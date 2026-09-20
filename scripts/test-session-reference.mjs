/** 当前已安装官方引用全链；仅读取TASK-010合成夹具，不访问生产会话。 */
import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {join,relative,dirname,resolve} from 'node:path';
import {tmpdir} from 'node:os';
import {mkdtempSync,globSync,readFileSync,copyFileSync,mkdirSync,rmSync} from 'node:fs';
import {createHash} from 'node:crypto';

const anchor=join(process.env.APPDATA,'npm/node_modules/@deepseek-ai/dsh/package.json');
const require=createRequire(anchor);
assert.equal(JSON.parse(readFileSync(require.resolve('@deepseek-ai/dsh-session-reference/package.json'),'utf8')).version,'0.1.5-rc.2','未知官方版本拒绝沿用验收');
const load=async name=>import(pathToFileURL(require.resolve(`@deepseek-ai/${name}`)).href);
const {Context}=await load('cordis');
const {default:SessionStore}=await load('dsh-session');
const {default:Persistence}=await load('dsh-session-persistence-jsonl');
const {default:Query}=await load('dsh-session-query-sqlite');
const {default:Resolver,formatSessionReferenceMention,parseSessionReferenceText}=await load('dsh-session-reference');
const profileRequire=createRequire(resolve(import.meta.dirname,'../.dsh/profiles/web/package.json'));
assert.equal(JSON.parse(readFileSync(profileRequire.resolve('dsh-session-link/package.json'),'utf8')).version,'0.2.1','未知session-link版本拒绝沿用验收');
const sessionLink=await import(pathToFileURL(profileRequire.resolve('dsh-session-link')).href);
const sourceRoot=resolve(import.meta.dirname,'../.dsh-upgrade-20260915/task010-tmp/root-ok');
const digest=path=>createHash('sha256').update(readFileSync(path)).digest('hex');

test('当前官方冷读引用：合成物理来源→context，异常失败关闭且源字节不变',async()=>{
  const work=mkdtempSync(join(tmpdir(),'dsh-session-reference-'));
  const root=join(work,'sessions');
  const ctx=new Context();
  const copied=[];
  try {
    const paths=globSync('**/session.v*.jsonl',{cwd:sourceRoot});
    assert.equal(paths.length,2,'必须是已知TASK-010两代合成会话，禁止扩大夹具来源');
    for(const tail of paths){
      const source=resolve(sourceRoot,tail);
      assert(!relative(sourceRoot,source).startsWith('..'));
      const header=JSON.parse(readFileSync(source,'utf8').split('\n')[0]);
      assert(JSON.stringify(header).includes('session-task010-synth-0001'),'来源不是已知合成ID');
      const target=join(root,tail);
      mkdirSync(dirname(target),{recursive:true});copyFileSync(source,target);
      copied.push({source,target,hash:digest(source)});
    }
    await ctx.plugin(SessionStore);
    await ctx.plugin(Persistence,{root,compression:'none'});
    await ctx.plugin(Query,{path:':memory:',openAt:'never'});
    await ctx.plugin(Resolver,{maxReferenceBytes:65536});
    const resolver=ctx.get('sessionReferenceResolver');
    const sourceId='session-task010-synth-0001';
    const agent={id:'session-reference-synthetic-target',session:{id:'session-reference-synthetic-target'},options:{}};
    const mention=formatSessionReferenceMention({sessionId:sourceId,label:'合成来源'});
    const parsed=parseSessionReferenceText(`请参考 ${mention}`);
    assert.equal(parsed.text,'请参考 @合成来源');
    assert.equal(parsed.references[0].sessionId,sourceId);
    const content=[{type:'text',text:parsed.text}];
    const result=await resolver.prepare(agent,content,parsed.references);
    assert.deepEqual(result.content,content);
    assert.notEqual(result.content,content,'返回必须脱离调用方可变对象');
    assert.equal(result.additionalContext.source.kind,'session-reference');
    assert.equal(result.additionalContext.source.references[0].sessionId,sourceId);
    assert.equal(result.additionalContext.source.references[0].capturedFormatVersion,3);
    const text=result.additionalContext.content[0].text;
    assert(text.includes('Synthetic final reply.'),'必须注入真实物理合成来源回答');
    assert(text.includes('untrusted, read-only'),'引用不得提升为系统指令');
    const repeated=await resolver.prepare(agent,content,[...parsed.references,...parsed.references]);
    assert.equal(repeated.additionalContext.source.references.length,1,'重复来源去重');
    await assert.rejects(resolver.prepare(agent,content,[{sessionId:agent.id}]),e=>e.code==='SESSION_REFERENCE_SELF_REFERENCE');
    await assert.rejects(resolver.prepare(agent,content,[{sessionId:'session-reference-missing-synthetic'}]),e=>e.code==='SESSION_REFERENCE_READ_FAILED');
    await assert.rejects(resolver.prepare(agent,content,['one','two','three','four'].map(sessionId=>({sessionId}))),e=>e.code==='SESSION_REFERENCE_TOO_MANY');
    assert.throws(()=>parseSessionReferenceText('@[坏引用](dsh-session:invalid)'),e=>e.code==='SESSION_REFERENCE_INVALID_REFERENCE');
    const cancellation=new AbortController();cancellation.abort();
    await assert.rejects(resolver.prepare(agent,content,parsed.references,cancellation.signal));
    // 当前安装 session-link 与官方 resolver 的真实 Cordis middleware 链。
    // 这里只替换不参与内容解析的 HTTP 路由注册，无网络服务或真实凭据。
    ctx.provide('webServer',{port:0,register:()=>()=>{}});
    await ctx.plugin(sessionLink);
    for(const text of [`参考 dsh://session/${sourceId}`,`参考 ${mention}`]){
      const direct={id:'synthetic-ref-message',role:'user',content:[{type:'text',text}],source:{kind:'user'}};
      const decision={kind:'accept',messages:[direct]};
      const resolved=await ctx.waterfall('agent/pre-step',{agent,turn:1,step:1},async()=>decision);
      const contexts=resolved.messages.filter(row=>row.source?.kind==='session-reference');
      assert.equal(contexts.length,1,'官方 resolver 与 session-link 共存必须仅注入一次');
      assert(contexts[0].content[0].text.includes('Synthetic final reply.'));
      assert.equal(decision.messages.length,1,'middleware不得原地改调用方决策');
    }
    for(const row of copied){assert.equal(digest(row.source),row.hash);assert.equal(digest(row.target),row.hash);}
  }finally{
    try { await ctx.fiber.dispose(); } finally {
      // 仅本测试mkdtemp创建的根，绝不删除源夹具或goal交付物。
      rmSync(work,{recursive:true,force:true});
    }
  }
});

test('仅有V2时只读引用逻辑迁移，不发布V3、不改源',async()=>{
  const work=mkdtempSync(join(tmpdir(),'dsh-session-reference-'));
  const root=join(work,'sessions');
  const ctx=new Context();
  try {
    const paths=globSync('**/session.v2.jsonl',{cwd:sourceRoot});
    assert.equal(paths.length,1);
    const source=resolve(sourceRoot,paths[0]);
    assert(!relative(sourceRoot,source).startsWith('..'));
    assert(JSON.parse(readFileSync(source,'utf8').split('\n')[0]).id==='session-task010-synth-0001');
    const target=join(root,paths[0]);mkdirSync(dirname(target),{recursive:true});copyFileSync(source,target);
    const hash=digest(target);
    await ctx.plugin(SessionStore);
    await ctx.plugin(Persistence,{root,compression:'none'});
    await ctx.plugin(Query,{path:':memory:',openAt:'never'});
    await ctx.plugin(Resolver,{maxReferenceBytes:65536});
    const result=await ctx.get('sessionReferenceResolver').prepare({id:'synthetic-target-v2',session:{id:'synthetic-target-v2'},options:{}},[{type:'text',text:'引用旧代合成来源'}],[{sessionId:'session-task010-synth-0001'}]);
    assert(result.additionalContext.content[0].text.includes('Synthetic final reply.'));
    assert.equal(result.additionalContext.source.references[0].capturedFormatVersion,3);
    assert.equal(digest(target),hash);
    assert.equal(digest(source),hash);
    assert.deepEqual(globSync('**/session.v*.jsonl',{cwd:root}),paths,'只读引用不得发布或覆盖新代');
  } finally {
    try {await ctx.fiber.dispose();} finally {rmSync(work,{recursive:true,force:true});}
  }
});
