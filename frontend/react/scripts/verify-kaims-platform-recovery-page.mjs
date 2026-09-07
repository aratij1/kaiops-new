import { chromium } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
const python = `import json,urllib.request
from common.config import get_settings
r=urllib.request.Request('http://localhost:8000/auth/login',data=json.dumps({'username':'admin','password':get_settings().admin_user_password}).encode(),headers={'Content-Type':'application/json'})
a=json.load(urllib.request.urlopen(r)); print(json.dumps({'accessToken':a['access_token'],'refreshToken':a.get('refresh_token',''),'username':'admin','password':get_settings().admin_user_password}))`;
const session = JSON.parse(execFileSync("docker", ["exec", "-i", "kaims-api-gateway-1", "python", "-"], { input: python, encoding: "utf8", windowsHide: true }));
const browser = await chromium.launch({headless:true});
const page = await browser.newPage({ viewport: { width: 1500, height: 1100 } });
try {

  const feeds = [];
  page.on("response", async (response) => { if(response.url().includes("/incidents/inbox/feed")) feeds.push({url:response.url(),status:response.status()}); });
  await page.goto("http://localhost:8501/incidents?inbox_view=resolved", {waitUntil:"domcontentloaded"});
  await page.locator('input[autocomplete="username"]').fill("admin");
  await page.locator('input[autocomplete="current-password"]').fill(session.password);
  await page.getByRole("button", {name:/sign in/i}).click();
  await page.locator(".kai-shell select").first().selectOption("KaiMS", {timeout:60000});
  const selected="4b1bcd2f-04b4-42ff-82d8-4f35bdc5a10a";
  let workspaceCalls=0;
  page.on("response",r=>{if(r.url().includes(`/incidents/${selected}/command`) && r.status()===200) workspaceCalls++;});
  await page.goto(`http://localhost:8501/incidents/${selected}`,{waitUntil:"domcontentloaded"});
  await page.getByRole("heading",{name:"Recovery independently verified",exact:true}).waitFor({timeout:30000});
  const checks=await page.locator(".ic-recovery-checks article").count();
  if(checks!==6) throw new Error(`Expected six recovery checks, got ${checks}`);
  const history=page.locator(".ic-investigation-history");
  if(await history.getAttribute("open")!==null) throw new Error("Historical investigation expanded by default");
  for(const value of ["Validation has not started","Waiting for execution evidence","No executable resolution is available","Record administrative closure","Submit reviewed evidence and rerun RCA"]){
    if(await page.getByText(value,{exact:true}).isVisible()) throw new Error(`Obsolete control: ${value}`);
  }
  const steps=await page.locator(".ic-journey li span").allTextContents();
  if(steps.includes("Executing") || steps.includes("Root cause")) throw new Error("Invented execution or causal milestone");
  await page.getByText("View 11 recorded samples",{exact:true}).first().click();
  if(await page.locator(".ic-recovery-checks article").first().locator("tbody tr").count()!==11) throw new Error("Missing recorded sample details");
  const before=workspaceCalls;await page.evaluate(()=>window.dispatchEvent(new Event("focus")));
  await page.waitForResponse(r=>r.url().includes(`/incidents/${selected}/command`)&&r.status()===200,{timeout:30000});
  await page.screenshot({path:"../../docs/architecture/kaims-platform-corrected-recovery-page-2026-09-07.png",fullPage:true});
  const result={incidentId:selected,checks,historicalInvestigationCollapsed:true,obsoleteControlsVisible:false,journey:steps,refreshOnFocus:workspaceCalls>before};
  writeFileSync("../../docs/architecture/kaims-platform-corrected-recovery-page-2026-09-07.json",JSON.stringify(result,null,2));
  const entry=await page.locator('script[type="module"][src]').first().getAttribute("src");
  await page.route("**/index.html",route=>route.fulfill({status:200,contentType:"text/html",body:'<html><script type="module" src="/assets/new-build-test.js"></script></html>'}));
  await page.evaluate(()=>window.dispatchEvent(new Event("focus")));
  await page.getByRole("button",{name:"Load updated page",exact:true}).waitFor({timeout:15000});
  if(await page.locator('script[type="module"][src]').first().getAttribute("src")!==entry) throw new Error("Update reloaded the page without user action");
  console.log(JSON.stringify({...result,sampleDetailsVisible:true,updateNoticeVerified:true,noAutomaticReload:true}));
} catch (error) {
  await page.screenshot({path:"../../docs/architecture/closed-inbox-browser-diagnostic.png",fullPage:true});
  console.log(JSON.stringify({url:page.url(),body:(await page.locator("body").innerText()).slice(-8000)}));
  throw error;
} finally { await browser.close(); }
