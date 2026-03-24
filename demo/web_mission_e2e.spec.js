const { chromium } = require('playwright')

const baseURL = process.env.BASE_URL || 'http://127.0.0.1:8876'

const scenarios = [
  {
    mode: 'solo',
    mission: 'SOLO WEB DEMO\nReply with exactly SOLO_WEB_OK.',
    channel: 'trunk',
  },
  {
    mode: 'trial',
    mission: 'TRIAL WEB DEMO\nCompare two possible approaches and output TRIAL_WEB_OK somewhere in the result.',
    channel: 'trial',
  },
  {
    mode: 'chain',
    mission: 'CHAIN WEB DEMO\nWork stage by stage and ensure the final output includes CHAIN_WEB_OK.',
    channel: 'chain',
  },
  {
    mode: 'swarm',
    mission: 'SWARM WEB DEMO\nParallelize independent work and ensure the combined output includes SWARM_WEB_OK.',
    channel: 'swarm',
  },
]

async function waitForStage(page) {
  const start = Date.now()
  while (Date.now() - start < 90000) {
    const text = (await page.getByTestId('console-stage').textContent()) || ''
    if (!text.includes('idle')) return text.trim()
    await page.waitForTimeout(1000)
  }
  throw new Error('console-stage stayed idle for 90s')
}

async function waitForTranscript(page) {
  const start = Date.now()
  while (Date.now() - start < 90000) {
    const count = await page.getByTestId('chat-message').count()
    const progress = (await page.getByTestId('console-progress').textContent()) || ''
    if (count >= 2 || /\b[1-9]\d*\b/.test(progress)) {
      return { count, progress: progress.trim() }
    }
    await page.waitForTimeout(1000)
  }
  throw new Error('visible transcript did not accumulate enough messages after 90s')
}

async function waitForLaunchReady(page) {
  const start = Date.now()
  while (Date.now() - start < 90000) {
    if (!(await page.getByTestId('launch-mission').isDisabled())) {
      return
    }
    await page.waitForTimeout(500)
  }
  throw new Error('launch button stayed disabled for 90s')
}

async function runScenario(page, scenario) {
  await page.getByTestId('mission-input').waitFor({ timeout: 15000 })
  await page.getByTestId(`mode-${scenario.mode}`).click()
  await page.getByTestId('mission-input').fill(scenario.mission)

  if (scenario.mode === 'swarm') {
    await page.getByTestId('swarm-message-0').waitFor({ timeout: 30000 })
    await page.getByTestId('swarm-message-0').fill('Return SWARM_UNIT_A_OK')
    await page.getByTestId('swarm-message-1').fill('Return SWARM_UNIT_B_OK')
  }

  await waitForLaunchReady(page)
  console.log(`[web-e2e] ${scenario.mode} input=${await page.getByTestId('mission-input').inputValue()}`)
  console.log(`[web-e2e] ${scenario.mode} disabled=${await page.getByTestId('launch-mission').isDisabled()}`)
  const missionResponsePromise = page.waitForResponse(response =>
    response.url().includes('/api/missions')
      && response.request().method() === 'POST'
      && response.status() === 201,
    { timeout: 120000 },
  )
  await page.getByTestId('launch-mission').click({ force: true })

  const missionResponse = await missionResponsePromise
  const mission = await missionResponse.json()
  const taskId = mission.task.id
  await page.getByTestId(`task-card-${taskId}`).waitFor({ timeout: 30000 })
  await page.getByTestId(`task-card-${taskId}`).click()
  await page.getByTestId(`console-channel-${scenario.channel}`).click()
  const stage = await waitForStage(page)
  const transcript = await waitForTranscript(page)
  console.log(`[web-e2e] ${scenario.mode} task=${taskId} stage=${stage} messages=${transcript.count} progress=${transcript.progress}`)
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage()
  page.on('console', msg => console.log(`[browser:${msg.type()}] ${msg.text()}`))
  page.on('pageerror', error => console.log(`[browser:error] ${error.message}`))
  page.on('request', request => {
    if (request.url().includes('/api/')) {
      console.log(`[browser:request] ${request.method()} ${request.url()}`)
    }
  })
  page.on('response', response => {
    if (response.url().includes('/api/')) {
      console.log(`[browser:response] ${response.status()} ${response.url()}`)
    }
  })

  try {
    await page.goto(baseURL, { waitUntil: 'domcontentloaded', timeout: 15000 })
    await page.getByTestId('mission-input').waitFor({ timeout: 15000 })
    for (const scenario of scenarios) {
      await runScenario(page, scenario)
    }
  } finally {
    await browser.close()
  }
}

main().catch(error => {
  console.error(error)
  process.exit(1)
})
