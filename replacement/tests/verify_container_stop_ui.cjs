// Read-only verification of the completed real container-stop recovery test.
const {chromium}=require('../../frontend/react/node_modules/@playwright/test');
const {execFileSync}=require('node:child_process');const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{
 const file=path.join(__dirname,'../container-stop-e2e-verification.json');const report=JSON.parse(fs.readFileSync(file,'utf8'));
 const info=JSON.parse(execFileSync('docker',['inspect','kaims-next-preview-api-1'],{encoding:'utf8',windowsHide:true}))[0];
 const token=info.Config.Env.find(v=>v.startsWith('NEXT_API_TOKEN=')).slice(15);
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8502/#/incidents/pipeline-validation/'+report.incident_id);
  await page.locator('#token').fill(token);await page.getByRole('button',{name:'Connect',exact:true}).click();
  await page.getByText('Recorded state: recovered',{exact:true}).waitFor();
  await page.goto('http://127.0.0.1:8502/#/alerts');
  const recovery=page.locator('#inbox-records .queue-card').filter({hasText:'ValidationContainerStopped'});
  await recovery.waitFor({timeout:30000});assert((await recovery.innerText()).toLowerCase().includes('recovered'));
  await recovery.getByRole('link',{name:'Review recovery'}).click();await page.getByText('Recorded state: recovered',{exact:true}).waitFor();
  assert((await page.locator('#impact').innerText()).includes('cannot serve requests'));
  assert((await page.locator('#rca').innerText()).includes('container is stopped'));
  assert((await page.locator('#resolution').innerText()).includes('Two fresh healthy observations'));
  assert((await page.locator('#journey').innerText()).includes('Recovery verified'));
  assert.deepEqual(errors,[]);
  report.ui_impact_rca_resolution_verified=true;report.browser_approval=false;
  fs.writeFileSync(file,JSON.stringify(report,null,2));console.log('Recovered incident, impact, cause, resolution and lifecycle verified in browser; no approval clicked.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
