// Approves only the disposable pipeline-validation repair, then verifies live recovery.
const {chromium}=require('../../frontend/react/node_modules/@playwright/test');
const {execFileSync}=require('node:child_process');const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{
 const file=path.join(__dirname,'../resolution-e2e-verification.json');const report=JSON.parse(fs.readFileSync(file,'utf8'));
 assert.equal(report.application,'pipeline-validation');
 const info=JSON.parse(execFileSync('docker',['inspect','kaims-next-preview-api-1'],{encoding:'utf8',windowsHide:true}))[0];
 const token=info.Config.Env.find(v=>v.startsWith('NEXT_API_TOKEN=')).slice(15);const base='http://127.0.0.1:8502';
 const endpoint='/applications/pipeline-validation/incidents/'+encodeURIComponent(report.incident_id);
 const headers={Authorization:'Bearer '+token};
 const initial=await(await fetch(base+endpoint,{headers})).json();
 assert.equal(initial.state,'awaiting_approval');assert.equal(initial.result.resolution.plan.action,'disable_test_maintenance');
 assert.equal(initial.result.resolution.plan.service,'validation-service');
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/#/incidents/pipeline-validation/'+report.incident_id);await page.locator('#token').fill(token);await page.getByRole('button',{name:'Connect',exact:true}).click();
  await page.getByText('Recorded state: awaiting approval',{exact:true}).waitFor();
  assert((await page.locator('#rca').innerText()).includes('test maintenance flag enabled'));
  assert((await page.locator('#impact').innerText()).includes('HTTP 503'));
  await page.getByRole('button',{name:'Approve and execute plan',exact:true}).click();
  await page.getByText('Recorded state: recovered',{exact:true}).waitFor({timeout:45000});
  assert((await page.locator('#resolution').innerText()).includes('Two fresh healthy observations'));
  assert((await page.locator('#journey').innerText()).includes('Recovery verified'));
  const row=await(await fetch(base+endpoint,{headers})).json();assert.equal(row.result.resolution.verification.length,2);
  const health=Number(execFileSync('docker',['exec','kaims-next-preview-api-1','python','-c',"import urllib.request; print(urllib.request.urlopen('http://validation-target:8080/health').status)"],{encoding:'utf8',windowsHide:true}).trim());
  assert.equal(health,200);
  const actionCount=Number(execFileSync('docker',['exec','kaims-next-preview-validation-target-1','python','-c',"import sqlite3; print(sqlite3.connect('/state/target.db').execute('SELECT COUNT(*) FROM actions').fetchone()[0])"],{encoding:'utf8',windowsHide:true}).trim());assert.equal(actionCount,1);
  assert.deepEqual(errors,[]);
  Object.assign(report,{final_state:row.state,final_health_status:health,actual_repair_count:actionCount,verification_observations:row.result.resolution.verification,
   real_rabbitmq:true,real_http_target:true,browser_approval:true,ui_impact_rca_resolution_verified:true});
  fs.writeFileSync(file,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
