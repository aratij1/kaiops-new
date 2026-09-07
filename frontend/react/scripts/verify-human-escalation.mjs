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
  await page.goto("http://localhost:8501/incidents", {waitUntil:"domcontentloaded"});
  await page.locator('input[autocomplete="username"]').fill("admin");
  await page.locator('input[autocomplete="current-password"]').fill(session.password);
  await page.getByRole("button", {name:/sign in/i}).click();
  await page.locator(".kai-shell select").first().selectOption("KaiMS", {timeout:60000});
  await page.getByRole("button", {name:"Incidents",exact:true}).first().click();
  const row=page.locator("tbody tr").filter({hasText:"ACTION REQUIRED"}).first();
  await row.getByRole("button",{name:/View details/i}).click({timeout:30000});
  const section=page.getByRole("region",{name:"Human escalation"});
  await section.getByRole("heading",{name:"Escalate to human agent"}).waitFor({timeout:30000});
  let intercepted=0;
  await page.route("**/incidents/*/escalate",route=>{
    intercepted++;
    return route.fulfill({status:409,contentType:"application/json",body:JSON.stringify({detail:{message:"No on-duty responder is available (browser test)."}})});
  });
  await section.getByLabel("Reason for escalation").fill("Please investigate the blocked resolution; browser verification only.");
  await section.getByRole("button",{name:"Escalate to human agent",exact:true}).click();
  await section.getByRole("alert").waitFor();
  if(intercepted!==1) throw new Error("Escalation request not intercepted exactly once");
  await page.goto("http://localhost:8501/incidents/4b1bcd2f-04b4-42ff-82d8-4f35bdc5a10a",{waitUntil:"domcontentloaded"});
  await page.getByRole("heading",{name:"Recovery independently verified",exact:true}).waitFor({timeout:30000});
  if(await page.getByRole("region",{name:"Human escalation"}).count()) throw new Error("Closed incident offers escalation");
  console.log(JSON.stringify({openIncidentFormVisible:true,errorShown:true,closedIncidentFormHidden:true,realHandoffsSubmitted:0}));
} finally { await browser.close(); }
