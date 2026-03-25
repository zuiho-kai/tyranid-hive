import { test, expect } from 'playwright/test'

const TASK_TITLE = '香港今天天气'
const PROMPT = `${TASK_TITLE}
请抓取香港今天的天气，返回温度、湿度、降雨概率和一句出门建议。不要反问，直接给结果。`
const SCREENSHOT_PATH = 'D:/虫群/tyranid-hive/docs/screenshots/playwright-weather-result.png'

async function sleep(ms) {
  await new Promise(resolve => setTimeout(resolve, ms))
}

test.setTimeout(600000)

test('weather task completes from dashboard flow', async ({ page, request }) => {
  await page.goto('/dashboard', { waitUntil: 'networkidle' })
  await page.getByTestId('mission-input').fill(PROMPT)
  await page.getByTestId('launch-mission').click()

  let taskId = null
  for (let i = 0; i < 30; i += 1) {
    const response = await request.get('/api/tasks')
    const tasks = await response.json()
    const found = tasks.find(task => (task.title || '').includes(TASK_TITLE))
    if (found) {
      taskId = found.id
      break
    }
    await sleep(1000)
  }

  expect(taskId).toBeTruthy()

  let finalTask = null
  const timeline = []
  for (let i = 0; i < 150; i += 1) {
    const response = await request.get(`/api/tasks/${taskId}`)
    const task = await response.json()
    finalTask = task
    timeline.push({
      tick: i,
      state: task.state,
      progress: task.progress_log.length,
      flow: task.flow_log.length,
      updated_at: task.updated_at,
    })
    if (['Complete', 'WaitingInput', 'Dormant', 'Cancelled'].includes(task.state)) {
      break
    }
    await sleep(2000)
  }

  await page.goto('/dashboard', { waitUntil: 'networkidle' })
  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true })

  console.log(JSON.stringify({
    taskId,
    finalState: finalTask?.state,
    title: finalTask?.title,
    blockers: finalTask?.meta?.analysis_blockers || [],
    flowLog: finalTask?.flow_log || [],
    progressLog: finalTask?.progress_log || [],
    timeline,
    screenshot: SCREENSHOT_PATH,
  }, null, 2))

  expect(finalTask?.state).toBe('Complete')
  expect((finalTask?.progress_log?.length || 0) > 0).toBeTruthy()
})
