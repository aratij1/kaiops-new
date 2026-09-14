// Read-only check of the running preview. Never prints or persists the access token.
const {chromium}=require('../../frontend/react/node_modules/@playwright/test');
const {execFileSync}=require('node:child_process');
const path=require('node:path');const fs=require('node:fs');const assert=require('node:assert/strict');
(async()=>{
 const token=execFileSync('docker',['exec','kaims-next-preview-api-1','python','-c','import os; print(os.environ["NEXT_API_TOKEN"])'],{encoding:'utf8',windowsHide:true}).trim();
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  await page.goto('http://127.0.0.1:8502/');await page.locator('#token').fill(token);await page.getByRole('button',{name:'Connect',exact:true}).click();
  await page.locator('#workspace-stats .stat').first().waitFor();
  const report={};
  for(const app of ['kaims','telemetry']){
   await page.evaluate(app=>{location.hash='#/applications/'+app+'/overview';},app);
   await page.waitForFunction(app=>document.getElementById('application-title').textContent===app && !document.getElementById('screen-application').hidden,app);
   const data=await page.evaluate(async ({app,token})=>{
    const headers={Authorization:'Bearer '+token};
    const overview=await (await fetch('/applications/'+app+'/overview',{headers})).json();
    const alerts=await (await fetch('/applications/'+app+'/live-alerts',{headers})).json();
    return {services:overview.services.length,documents:overview.documents.length,incidents:overview.incidents.total,health:overview.health.status,discovery:overview.discovery_state,alerts:alerts.status,alert_count:alerts.alerts.length,alert_sources:alerts.source_outcomes};
   },{app,token});
   assert(data.services>0 && data.documents===({kaims:18,telemetry:28}[app]) && data.discovery==='context_ready');
   await page.locator('#application-tabs').getByRole('link',{name:'Documents',exact:true}).click();
   await page.getByRole('button',{name:'Read document contents'}).click();
   await page.locator('#overview-document-content summary').first().waitFor();
   assert.equal(await page.locator('#overview-document-content summary').count(),data.documents);
   report[app]=data;
   await page.locator('#application-tabs').getByRole('link',{name:'Services',exact:true}).click();
   await page.locator('#overview-services .app-card').first().waitFor();
   assert.equal(await page.locator('#overview-services .app-card').count(),data.services);
  }
  const health=await (await fetch('http://127.0.0.1:8502/healthz')).json();assert(health.broker_ready);
  report.broker_ready=true;report.read_only=true;
  fs.writeFileSync(path.resolve(__dirname,'../overview-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
