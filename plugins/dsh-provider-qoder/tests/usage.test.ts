import test from 'node:test'
import assert from 'node:assert/strict'
import { QoderAuthService } from '../src/qoder/transport/auth.ts'
import { QoderLlmError } from '../src/qoder/errors.ts'
import { QoderUsageReader } from '../src/qoder/transport/account-reader.ts'

test('QoderUsageReader reads subscriber profile and quota usage, and caches within TTL', async () => {
  let quotaCalls = 0
  const diagnostics: string[] = []
  const fetchMock = async (input: RequestInfo | URL): Promise<Response> => {
    const url = String(input)
    if (url.includes('/jobToken/exchange')) {
      return new Response(JSON.stringify({ token: 'jt-quota-test', expires_in: 3_600_000 }), { status: 200 })
    }
    if (url.includes('/userinfo')) {
      return new Response(JSON.stringify({ id: 'user-123', email: 'dev@qoder.sh', name: 'Qoder Dev' }))
    }
    if (url.includes('/quota/usage')) {
      quotaCalls++
      return new Response(
        JSON.stringify({
          userId: 'user-123',
          userType: 'teams',
          totalUsagePercentage: 0.03,
          isQuotaExceeded: false,
          expiresAt: 1790756471159,
          userQuota: {
            total: 3000.0,
            used: 84.0,
            remaining: 2916.0,
            percentage: 0.03,
            unit: 'credits',
          },
          orgResourcePackage: {
            used: 0.0,
            remaining: 3000.0,
            percentage: 0.0,
            unit: 'credits',
            cap: 3000.0,
            available: true,
          },
        }),
        { status: 200 },
      )
    }
    throw new Error(`unexpected URL: ${url}`)
  }

  const authService = new QoderAuthService({
    fetch: fetchMock as typeof fetch,
    resolveMachineId: () => 'machine-test',
  })
  const reader = new QoderUsageReader({
    authService,
    fetch: fetchMock as typeof fetch,
    ttlMs: 60_000,
    logger: {
      debug: (message, ...details) => diagnostics.push(JSON.stringify([message, ...details])),
    },
  })

  const first = await reader.readAccount('pt-test')
  assert.equal(first.profile.id, 'user-123')
  assert.equal(first.profile.name, 'Qoder Dev')
  assert.equal(first.profile.email, 'dev@qoder.sh')
  assert.equal(first.usage?.userQuota?.total, 3000)
  assert.equal(first.usage?.userQuota?.used, 84)
  assert.equal(first.usage?.userQuota?.remaining, 2916)
  assert.equal(first.usage?.orgResourcePackage?.total, 3000)
  assert.equal(first.usage?.orgResourcePackage?.used, 0)
  assert.equal(first.usage?.orgResourcePackage?.remaining, 3000)
  assert.equal(first.usage?.dedicatedResourcePackages, undefined)
  assert.equal(quotaCalls, 1)
  assert.match(diagnostics.join('\n'), /account\.usage/)


  // Cache hit
  const second = await reader.readAccount('pt-test')
  assert.equal(second, first)
  assert.equal(quotaCalls, 1)

  // Force refresh
  const third = await reader.readAccount('pt-test', { force: true })
  assert.equal(quotaCalls, 2)
  assert.equal(third.profile.name, 'Qoder Dev')
})

test('QoderUsageReader surfaces quota failures and does not cache them', async () => {
  let quotaCalls = 0
  const fetchMock = async (input: RequestInfo | URL): Promise<Response> => {
    const url = String(input)
    if (url.includes('/jobToken/exchange')) {
      return new Response(JSON.stringify({ token: 'jt-quota-test', expires_in: 3_600_000 }), { status: 200 })
    }
    if (url.includes('/userinfo')) {
      return new Response(JSON.stringify({ id: 'user-456', email: 'error@qoder.sh', name: 'Error Case' }))
    }
    if (url.includes('/quota/usage')) {
      quotaCalls++
      return new Response(JSON.stringify({ message: 'Internal Server Error' }), { status: 500 })
    }
    throw new Error(`unexpected URL: ${url}`)
  }

  const authService = new QoderAuthService({
    fetch: fetchMock as typeof fetch,
    resolveMachineId: () => 'machine-test',
  })
  const reader = new QoderUsageReader({
    authService,
    fetch: fetchMock as typeof fetch,
  })

  await assert.rejects(reader.readAccount('pt-error-test'), (error: Error) => {
    assert.ok(error instanceof QoderLlmError)
    assert.equal((error as QoderLlmError).code, 'SERVER')
    assert.equal((error as QoderLlmError).failure.status, 500)
    return true
  })
  await assert.rejects(reader.readAccount('pt-error-test'))
  assert.equal(quotaCalls, 4)
})

test('QoderUsageReader propagates caller cancellation and does not cache the partial account', async () => {
  let quotaCalls = 0
  let quotaCanSucceed = false
  let notifyUsageStarted: (() => void) | undefined
  const usageStarted = new Promise<void>(resolve => { notifyUsageStarted = resolve })
  const fetchMock = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = String(input)
    if (url.includes('/jobToken/exchange')) {
      return new Response(JSON.stringify({ token: 'jt-abort-test', expires_in: 3_600_000 }))
    }
    if (url.includes('/userinfo')) {
      return new Response(JSON.stringify({ id: 'user-abort', name: 'Abort Case' }))
    }
    if (url.includes('/quota/usage')) {
      quotaCalls++
      if (quotaCanSucceed) {
        return new Response(JSON.stringify({ userQuota: { total: 10, used: 1, remaining: 9, unit: 'credits' } }))
      }
      notifyUsageStarted?.()
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true })
      })
    }
    throw new Error(`unexpected URL: ${url}`)
  }
  const authService = new QoderAuthService({
    fetch: fetchMock as typeof fetch,
    resolveMachineId: () => 'machine-test',
  })
  const reader = new QoderUsageReader({ authService, fetch: fetchMock as typeof fetch })
  const controller = new AbortController()
  const request = reader.readAccount('pt-abort-test', { signal: controller.signal })
  await usageStarted
  controller.abort()

  await assert.rejects(request, (error: Error) => {
    assert.ok(error instanceof QoderLlmError)
    assert.equal((error as QoderLlmError).code, 'ABORTED')
    return true
  })

  quotaCanSucceed = true
  const retry = await reader.readAccount('pt-abort-test')
  assert.equal(retry.usage?.userQuota?.remaining, 9)
  assert.equal(quotaCalls, 2)
})

test('QoderUsageReader bounds a stalled quota request with its own timeout', async () => {
  const fetchMock = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = String(input)
    if (url.includes('/jobToken/exchange')) {
      return new Response(JSON.stringify({ token: 'jt-timeout-test', expires_in: 3_600_000 }))
    }
    if (url.includes('/userinfo')) {
      return new Response(JSON.stringify({ id: 'user-timeout', name: 'Timeout Case' }))
    }
    if (url.includes('/quota/usage')) {
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('timed out', 'TimeoutError')), { once: true })
      })
    }
    throw new Error(`unexpected URL: ${url}`)
  }
  const authService = new QoderAuthService({
    fetch: fetchMock as typeof fetch,
    resolveMachineId: () => 'machine-test',
  })
  const reader = new QoderUsageReader({
    authService,
    fetch: fetchMock as typeof fetch,
    timeoutMs: 5,
  })

  await assert.rejects(reader.readAccount('pt-timeout-test'), (error: Error) => {
    assert.ok(error instanceof QoderLlmError)
    assert.equal((error as QoderLlmError).code, 'TIMEOUT')
    return true
  })
})

test('QoderUsageReader shares a concurrent quota cache miss', async () => {
  let quotaCalls = 0
  const fetchMock = async (input: RequestInfo | URL): Promise<Response> => {
    const url = String(input)
    if (url.includes('/jobToken/exchange')) return new Response(JSON.stringify({ token: 'jt-shared' }))
    if (url.includes('/userinfo')) return new Response(JSON.stringify({ id: 'user-shared' }))
    if (url.includes('/quota/usage')) {
      quotaCalls++
      await new Promise(resolve => setTimeout(resolve, 5))
      return new Response(JSON.stringify({ userQuota: { total: 10, used: 1, remaining: 9 } }))
    }
    throw new Error(`unexpected URL: ${url}`)
  }
  const authService = new QoderAuthService({
    fetch: fetchMock as typeof fetch,
    resolveMachineId: () => 'machine-test',
  })
  const reader = new QoderUsageReader({ authService, fetch: fetchMock as typeof fetch })

  const [first, second] = await Promise.all([
    reader.readAccount('pt-shared'),
    reader.readAccount('pt-shared'),
  ])
  assert.equal(quotaCalls, 1)
  assert.equal(first, second)
})

test('QoderUsageReader reads subscriber plan and user status with machine fingerprint headers', async () => {
  let statusHeaders: Record<string, string> | undefined
  let planHeaders: Record<string, string> | undefined
  let quotaHeaders: Record<string, string> | undefined
  const fetchMock = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = String(input)
    if (url.includes('/jobToken/exchange')) {
      return new Response(JSON.stringify({ token: 'jt-plan-test', expires_in: 3_600_000 }))
    }
    if (url.includes('/userinfo')) {
      return new Response(JSON.stringify({ id: 'user-plan-1', email: 'pro@qoder.sh', name: 'Pro Dev' }))
    }
    if (url.includes('/quota/usage')) {
      quotaHeaders = init?.headers as Record<string, string>
      return new Response(JSON.stringify({ userQuota: { total: 100, used: 20, remaining: 80, unit: 'credits' } }))
    }
    if (url.includes('/user/plan')) {
      planHeaders = init?.headers as Record<string, string>
      return new Response(
        JSON.stringify({
          user_type: 'pro',
          plan_tier_name: 'Pro',
          is_personal_version: false,
          is_highest_tier: true,
          start_date: 1700000000000,
          end_date: 1735689600000,
          organization: {
            org_id: 'org-456',
            org_name: 'DeepSeek Harness Team',
            role_name: 'Owner',
            is_suspended: false,
            can_manage_subscriptions: true,
            resource_package_feature_enabled: true,
          },
          feature_allowed: {
            quest: true,
            wiki: true,
            code_review: true,
          },
        }),
      )
    }
    if (url.includes('/user/status')) {
      statusHeaders = init?.headers as Record<string, string>
      return new Response(
        JSON.stringify({
          featureSwitches: { allow_byok: 2 },
          teamSwitches: { allow_byok: 2 },
          isPrivacyPolicyModifiable: true,
        }),
      )
    }
    throw new Error(`unexpected URL: ${url}`)
  }

  const authService = new QoderAuthService({
    fetch: fetchMock as typeof fetch,
    resolveMachineId: () => 'umid-fingerprint-test',
  })
  const reader = new QoderUsageReader({
    authService,
    fetch: fetchMock as typeof fetch,
  })

  const account = await reader.readAccount('pt-full-test')
  assert.equal(account.profile.name, 'Pro Dev')
  assert.equal(account.plan?.userType, 'pro')
  assert.equal(account.plan?.planTierName, 'Pro')
  assert.equal(account.plan?.isPersonalVersion, false)
  assert.equal(account.plan?.isHighestTier, true)
  assert.equal(account.plan?.organization?.orgName, 'DeepSeek Harness Team')
  assert.equal(account.plan?.organization?.isSuspended, false)
  assert.equal(account.plan?.featureAllowed?.codeReview, true)

  assert.equal(account.status?.allowByok, 2)
  assert.equal(account.status?.teamAllowByok, 2)
  assert.equal(account.status?.isPrivacyPolicyModifiable, true)

  assert.equal(planHeaders?.authorization, 'Bearer jt-plan-test')
  assert.equal(statusHeaders?.authorization, 'Bearer jt-plan-test')
  assert.equal(statusHeaders?.['Cosy-MachineToken'], 'umid-fingerprint-test')
  assert.equal(statusHeaders?.['Cosy-MachineType'], 'host')
  assert.equal(planHeaders?.['user-agent'], 'qoder/1.1.47')
  assert.equal(statusHeaders?.['user-agent'], 'qoder/1.1.47')
  assert.equal(quotaHeaders?.['user-agent'], 'qoder/1.1.47')
  assert.equal(planHeaders?.['cosy-clienttype'], '5')
  assert.equal(statusHeaders?.['cosy-clienttype'], '5')
  assert.equal(quotaHeaders?.['cosy-clienttype'], '5')
})

test('QoderUsageReader normalizes dedicated resource packages and skips unusable entries', async () => {
  const usagePayload = {
    userId: 'user-pkg',
    userType: 'teams',
    totalUsagePercentage: 0.89,
    isQuotaExceeded: false,
    expiresAt: 1790822453000,
    userQuota: { total: 3000, used: 3000, remaining: 0, percentage: 1, unit: 'credits' },
    dedicatedResourcePackages: [
      {
        id: 'pkg-0001',
        name: 'act-20260918-468',
        description: 'growth-campaign:act-20260918-468:grant:internal',
        total: 2000,
        used: 1425,
        remaining: 575,
        percentage: 0.72,
        unit: 'credits',
        expiresAt: 1789790399000,
        available: true,
        status: 'QUOTA_DETAIL_STATUS_ACTIVE',
        displayLabels: [
          {
            dimension: 'description',
            value: 'sota model series description',
            valueI18n: {
              'en-US': 'SOTA Exclusive Credits: used first when you select the Sonus model in the model selector.',
              'zh-CN': 'SOTA 专属积分：在模型选择器中选择 Sonus 模型时优先抵扣该积分。',
            },
          },
          {
            dimension: 'title',
            value: 'sota model series',
            valueI18n: {
              'en-US': 'SOTA Exclusive Credits',
              'zh-CN': 'SOTA 专属积分',
            },
          },
        ],
      },
      {
        id: 'pkg-0002',
        cap: 500,
        used: 100,
        remaining: 400,
        percentage: 0.2,
        unit: 'credits',
        // A malformed container must degrade to "no copy" instead of throwing.
        displayLabels: { dimension: 'title', value: 'not an array' },
      },
      { name: 'empty', total: 0, used: 0, remaining: 0 },
      null,
    ],
  }
  const fetchMock = async (input: RequestInfo | URL): Promise<Response> => {
    const url = String(input)
    if (url.includes('/jobToken/exchange')) {
      return new Response(JSON.stringify({ token: 'jt-package-test', expires_in: 3_600_000 }))
    }
    if (url.includes('/userinfo')) {
      return new Response(JSON.stringify({ id: 'user-pkg', email: 'pkg@qoder.sh', name: 'Package Dev' }))
    }
    if (url.includes('/quota/usage')) {
      return new Response(JSON.stringify(usagePayload))
    }
    throw new Error(`unexpected URL: ${url}`)
  }
  const authService = new QoderAuthService({
    fetch: fetchMock as typeof fetch,
    resolveMachineId: () => 'machine-test',
  })
  const reader = new QoderUsageReader({ authService, fetch: fetchMock as typeof fetch })

  const account = await reader.readAccount('pt-package-test')
  const packages = account.usage?.dedicatedResourcePackages
  assert.ok(packages)
  assert.equal(packages.length, 2)

  const [first, second] = packages
  assert.equal(first.id, 'pkg-0001')
  assert.equal(first.total, 2000)
  assert.equal(first.used, 1425)
  assert.equal(first.remaining, 575)
  assert.equal(first.percentage, 72)
  assert.equal(first.unit, 'credits')
  assert.equal(first.expiresAt, new Date(1789790399000).toISOString())
  assert.equal(first.available, true)
  assert.equal(first.status, 'QUOTA_DETAIL_STATUS_ACTIVE')
  assert.equal(first.title?.fallback, 'sota model series')
  assert.equal(first.title?.values['zh-CN'], 'SOTA 专属积分')
  assert.equal(first.title?.values['en-US'], 'SOTA Exclusive Credits')
  assert.equal(first.description?.fallback, 'sota model series description')
  assert.equal(first.description?.values['zh-CN'], 'SOTA 专属积分：在模型选择器中选择 Sonus 模型时优先抵扣该积分。')
  // The internal growth-campaign identifiers must never ride the normalized copy.
  assert.doesNotMatch(JSON.stringify(packages), /act-20260918-468/u)
  // ...nor the raw upstream echo that shares the payload sent to the client.
  assert.doesNotMatch(JSON.stringify(account.usage), /act-20260918-468|growth-campaign/u)
  const rawUsage = account.usage?.raw as Record<string, unknown> | undefined
  assert.equal(rawUsage?.dedicatedResourcePackages, undefined)
  assert.equal(rawUsage?.userType, 'teams')

  assert.equal(second.id, 'pkg-0002')
  assert.equal(second.total, 500)
  assert.equal(second.used, 100)
  assert.equal(second.remaining, 400)
  assert.equal(second.percentage, 20)
  assert.equal(second.title, undefined)
  assert.equal(second.description, undefined)
  assert.equal(second.expiresAt, undefined)
})

test('QoderUsageReader tolerates an out-of-range expiry instead of failing the account read', async () => {
  // int64 max is the provider's "never expires" sentinel and sits far outside
  // the Date range, so it must degrade to "no expiry" rather than throw.
  const payload = {
    userQuota: { total: 3000, used: 3000, remaining: 0, percentage: 1, unit: 'credits' },
    expiresAt: 9_223_372_036_854_775_807,
    dedicatedResourcePackages: [
      {
        id: 'pkg-never',
        total: 2000,
        used: 10,
        remaining: 1990,
        expiresAt: 9_223_372_036_854_775_807,
      },
    ],
  }
  const fetchMock = async (input: RequestInfo | URL): Promise<Response> => {
    const url = String(input)
    if (url.includes('/jobToken/exchange')) return new Response(JSON.stringify({ token: 'jt-sentinel' }))
    if (url.includes('/userinfo')) return new Response(JSON.stringify({ id: 'user-sentinel' }))
    if (url.includes('/quota/usage')) return new Response(JSON.stringify(payload))
    throw new Error(`unexpected URL: ${url}`)
  }
  const authService = new QoderAuthService({
    fetch: fetchMock as typeof fetch,
    resolveMachineId: () => 'machine-test',
  })
  const reader = new QoderUsageReader({ authService, fetch: fetchMock as typeof fetch })

  const account = await reader.readAccount('pt-sentinel')
  assert.equal(account.usage?.expiresAt, undefined)
  const [pkg] = account.usage?.dedicatedResourcePackages ?? []
  assert.equal(pkg?.expiresAt, undefined)
  assert.equal(pkg?.remaining, 1990)
  assert.equal(account.usage?.userQuota?.total, 3000)
})

test('QoderUsageReader omits dedicated resource packages for an absent or non-array field', async () => {
  let payload: Record<string, unknown> = { userQuota: { total: 10, used: 1, remaining: 9 } }
  const fetchMock = async (input: RequestInfo | URL): Promise<Response> => {
    const url = String(input)
    if (url.includes('/jobToken/exchange')) return new Response(JSON.stringify({ token: 'jt-no-pkg' }))
    if (url.includes('/userinfo')) return new Response(JSON.stringify({ id: 'user-no-pkg' }))
    if (url.includes('/quota/usage')) return new Response(JSON.stringify(payload))
    throw new Error(`unexpected URL: ${url}`)
  }
  const authService = new QoderAuthService({
    fetch: fetchMock as typeof fetch,
    resolveMachineId: () => 'machine-test',
  })
  const reader = new QoderUsageReader({ authService, fetch: fetchMock as typeof fetch })

  const absent = await reader.readAccount('pt-no-pkg')
  assert.equal(absent.usage?.dedicatedResourcePackages, undefined)

  payload = { userQuota: { total: 10, used: 1, remaining: 9 }, dedicatedResourcePackages: 'not an array' }
  const malformed = await reader.readAccount('pt-no-pkg', { force: true })
  assert.equal(malformed.usage?.dedicatedResourcePackages, undefined)

  payload = { userQuota: { total: 10, used: 1, remaining: 9 }, dedicatedResourcePackages: [] }
  const empty = await reader.readAccount('pt-no-pkg', { force: true })
  assert.equal(empty.usage?.dedicatedResourcePackages, undefined)
  assert.equal(empty.usage?.userQuota?.remaining, 9)
})

test('QoderUsageReader degrades gracefully when plan or status endpoint returns error', async () => {
  const fetchMock = async (input: RequestInfo | URL): Promise<Response> => {
    const url = String(input)
    if (url.includes('/jobToken/exchange')) {
      return new Response(JSON.stringify({ token: 'jt-degrade-test', expires_in: 3_600_000 }))
    }
    if (url.includes('/userinfo')) {
      return new Response(JSON.stringify({ id: 'user-deg', email: 'deg@qoder.sh', name: 'Degrading Dev' }))
    }
    if (url.includes('/quota/usage')) {
      return new Response(JSON.stringify({ userQuota: { total: 50, used: 10, remaining: 40, unit: 'credits' } }))
    }
    if (url.includes('/user/plan')) {
      return new Response(JSON.stringify({ error: 'Plan service unavailable' }), { status: 503 })
    }
    if (url.includes('/user/status')) {
      return new Response(JSON.stringify({ error: 'Status not found' }), { status: 404 })
    }
    throw new Error(`unexpected URL: ${url}`)
  }

  const authService = new QoderAuthService({
    fetch: fetchMock as typeof fetch,
    resolveMachineId: () => 'machine-deg',
  })
  const reader = new QoderUsageReader({
    authService,
    fetch: fetchMock as typeof fetch,
  })

  const account = await reader.readAccount('pt-degrade-test')
  assert.equal(account.profile.name, 'Degrading Dev')
  assert.equal(account.usage?.userQuota?.remaining, 40)
  assert.equal(account.plan, undefined)
  assert.equal(account.status, undefined)
})
