import { useMemo, useState } from 'react'
import type { QoderCatalogModel } from '../qoder/catalog.ts'
import {
  reconcileQoderModels,
  type QoderCredentialOperations,
  type QoderCredentialInjected,
} from './credential-operations.ts'
import type { QoderCredentialCopy } from './locales.ts'
import css from './QoderCredentialCard.module.css'

interface QoderModelCatalogProps extends Pick<QoderCredentialInjected, 't'> {
  operations: Pick<QoderCredentialOperations, 'discoverModels'>
  models: QoderCatalogModel[]
  disabled: boolean
  onChange(models: QoderCatalogModel[]): void
}

export function validateModelCatalog(models: readonly QoderCatalogModel[]): QoderCredentialCopy | undefined {
  return models.length === 0 ? 'modelsRequired' : undefined
}

export function QoderModelCatalog(props: QoderModelCatalogProps) {
  const { operations, models, disabled, onChange, t } = props
  const [fetching, setFetching] = useState(false)
  const [failure, setFailure] = useState<string | undefined>()
  const [catalog, setCatalog] = useState<QoderCatalogModel[] | undefined>()
  const [unavailableIds, setUnavailableIds] = useState<Set<string>>(new Set())
  const displayedModels = catalog ?? models
  const selectedIds = useMemo(() => new Set(models.map(model => model.id)), [models])

  const fetchModels = async (): Promise<void> => {
    setFetching(true)
    setFailure(undefined)
    const result = await operations.discoverModels()
    setFetching(false)
    if (!result.ok) {
      setFailure(result.error.message || t('modelsFetchFailed'))
      return
    }
    const reconciled = reconcileQoderModels(catalog ?? models, result.value)
    setCatalog(reconciled.catalog)
    setUnavailableIds(reconciled.unavailableIds)
    onChange(reconciled.selected)
  }

  const toggleModel = (id: string, enabled: boolean): void => {
    if (unavailableIds.has(id)) return
    const source = catalog ?? models
    if (catalog === undefined) setCatalog(source)
    const nextSelected = new Set(selectedIds)
    if (enabled) nextSelected.add(id)
    else nextSelected.delete(id)
    onChange(source.filter(model => nextSelected.has(model.id) && !unavailableIds.has(model.id)))
  }

  return (
    <section className={css.modelCatalog} aria-label={t('modelsTitle')}>
      <div className={css.modelCatalogHead}>
        <div>
          <strong className={css.modelCatalogTitle}>{t('modelsTitle')}</strong>
          <p className={css.modelCatalogMeta}>{t('modelsEnabled', { count: models.length })}</p>
        </div>
        <button
          type="button"
          className={css.linkButton}
          disabled={disabled || fetching}
          onClick={() => { void fetchModels() }}
        >
          {fetching ? t('modelsFetching') : t('modelsFetch')}
        </button>
      </div>
      {failure ? <p className={css.error} role="alert">{failure}</p> : null}
      <div className={css.modelList}>
        {displayedModels.map(model => {
          const unavailable = unavailableIds.has(model.id)
          return (
            <label className={`${css.modelChoice} ${unavailable ? css.modelUnavailable : ''}`} key={model.id}>
              <input
                type="checkbox"
                checked={!unavailable && selectedIds.has(model.id)}
                disabled={disabled || unavailable}
                onChange={event => { toggleModel(model.id, event.currentTarget.checked) }}
              />
              <span className={css.modelChoiceName}>{model.name}</span>
              <span className={css.modelRate}>
                {model.priceFactor === undefined
                  ? t('modelRateUnknown')
                  : t('modelRate', { value: model.priceFactor })}
              </span>
              <code>{model.id}</code>
              {unavailable ? <span className={css.modelBadge}>{t('modelUnavailable')}</span> : null}
            </label>
          )
        })}
      </div>
    </section>
  )
}
