/** 真实已安装知识库；合成上下文及专属临时DB，禁止模型调用和生产数据读取。 */
import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve,join} from 'node:path';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
const require=createRequire(resolve(import.meta.dirname,'../.dsh/profiles/web/package.json'));
const {Context}=await import(pathToFileURL(require.resolve('@deepseek-ai/cordis')).href);
const {default:knowledge}=await import(pathToFileURL(require.resolve('dsh-knowledge-sqlite')).href);

test('已安装知识库：中文FTS5/重启续读/ask/global与workspace隔离',async()=>{
  const work=mkdtempSync(join(tmpdir(),'dsh-knowledge-installed-'));
  const databasePath=join(work,'synthetic.sqlite');
  const instances=[];
  const state={workspace:'F:/synthetic-knowledge-a',session:'synthetic-session-a',calls:0};
  const boot=async()=>{
    const ctx=new Context();instances.push(ctx);
    const registered=[];
    ctx.provide('agents',{currentInitiator:()=>({id:state.session,session:{id:state.session,header:{cwd:state.workspace}},ctx})});
    ctx.provide('tools',{register:tool=>{registered.push(tool.name);return()=>{};}});
    ctx.provide('timer',{interval:()=>()=>{},timeout:()=>()=>{}});
    ctx.provide('llm',{stream:()=>{state.calls++;throw new Error('本验收禁止模型调用');}});
    const fiber=ctx.plugin(knowledge,{databasePath,gating:'ask',registerProbeTool:false,queryExpansion:{enabled:false},authorization:{allowedGlobalWriters:[]}});
    await fiber.await();
    assert.deepEqual(registered.sort(),['knowledge_delete','knowledge_list','knowledge_search','knowledge_update','knowledge_write']);
    for(const name of ['knowledge_write','knowledge_update','knowledge_delete']){
      const result=await ctx.waterfall('tools/pre-execute',{name},async()=>({kind:'allow'}));
      assert.equal(result.kind,'ask', `${name}不得自动放行`);
    }
    assert.equal((await ctx.waterfall('tools/pre-execute',{name:'knowledge_search'},async()=>({kind:'allow'}))).kind,'allow');
    return {ctx,service:ctx.get('knowledge')};
  };
  try{
    let app=await boot();
    // 已明确授权的合成数据seed经服务写入；模型工具自身仍保持ask。
    const written=await app.service.write({content:'部署流程：先编译，再启动服务；仅供合成知识库验收。',scope:'workspace',dedupeKey:'synthetic-restart'});
    assert(!('error' in written));
    const search=await app.service.search('部署流程');
    assert(JSON.stringify(search).includes(written.id),'中文trigram必须命中');
    const global=await app.service.write({content:'合成global拒绝验证',scope:'global'});
    assert.equal(global.error?.code,'write-rejected');
    await app.ctx.fiber.dispose();
    app=await boot();
    assert(JSON.stringify(await app.service.search('部署流程')).includes(written.id),'重建服务必须续读同一合成DB');
    state.workspace='F:/synthetic-knowledge-b';state.session='synthetic-session-b';
    assert(!JSON.stringify(await app.service.search('部署流程')).includes(written.id),'不得检索其他workspace');
    const rejected=await app.service.delete(written.id);
    assert('error' in rejected,'不得删除其他workspace');
    assert.equal(state.calls,0);
  }finally{
    try{for(const ctx of instances.reverse())await ctx.fiber.dispose();}finally{rmSync(work,{recursive:true,force:true});}
  }
});
