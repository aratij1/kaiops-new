// Read-only browser verification against the running preview.
const {chromium}=require('../../frontend/react/node_modules/@playwright/test');
const {execFileSync}=require('node:child_process');const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{
 const info=JSON.parse(execFileSync('docker',['inspect','kaims-next-preview-api-1'],{encoding:'utf8',windowsHide:true}))[0];
 const token=info.Config.Env.find(v=>v.startsWith('NEXT_API_TOKEN=')).slice('NEXT_API_TOKEN='.length);
 const report=JSON.parse(fs.readFileSync(path.join(__dirname,'../live-monitoring-verification.json'),'utf8'));
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8502/#/alerts');await page.locator('#token').fill(token);await page.getByRole('button',{name:'Connect',exact:true}).click();
  await page.locator('#alert-coverage').getByText('kaims: collected',{exact:true}).waitFor();
  await page.locator('#alert-coverage').getByText('telemetry: collected',{exact:true}).waitFor();
  const cards=await page.locator('#alert-records .alert-card').count();
  if(cards){await page.locator('#alert-records').getByRole('link',{name:'Open investigation',exact:true}).first().click();await page.locator('#incident-state').waitFor({state:'visible'});}
  for(const [app,check]of Object.entries(report.checks)){
   await page.evaluate(({app,id})=>{location.hash='#/incidents/'+app+'/'+id;},{app,id:check.incident_id});
   await page.waitForFunction(service=>document.getElementById('window').textContent.startsWith(service+' /')&&!document.getElementById('screen-incident').hidden,check.service);
   assert.equal(await page.locator('#incident-state').textContent(),'Recorded state: assessed');
   assert((await page.locator('#outcomes').innerText()).includes('partial'));
   await page.getByRole('button',{name:'Collected evidence',exact:true}).click();await page.locator('#artifact-content .document-row').first().waitFor();
   check.browser_verified=true;
  }
  await page.evaluate(()=>{location.hash='#/alerts';});await page.locator('#alert-records').waitFor({state:'visible'});
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(errors,[]);report.alerts_ui={browser_verified:true,live_alert_cards:cards,mobile_layout:true};
  fs.writeFileSync(path.join(__dirname,'../live-monitoring-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({alerts_ui:report.alerts_ui,checks:report.checks}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
