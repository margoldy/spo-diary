import { test, expect } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import path from 'node:path'

async function login(page) {
  await page.goto('/login')
  await page.getByLabel('Имя', { exact: true }).fill('Дарья')
  await page.getByLabel('Электронная почта').fill(`ui-${randomUUID()}@example.com`)
  await page.getByRole('button', { name: 'Получить код' }).click()
  await page.getByLabel('Код из письма').fill('314159')
  await page.getByRole('button', { name: 'Продолжить' }).click()
  await expect(page).toHaveURL(/\/catalog$/)
  await expect(page.locator('.work-card')).toHaveCount(12)
}
const dialog = (page) => page.getByRole('dialog')

test('регистрация, неверный код, профиль и выход', async ({ page }) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/library')
  await expect(page).toHaveURL(/\/login/)
  await page.screenshot({ path: 'test-results/login-desktop.png', fullPage: true })
  await page.getByLabel('Имя', { exact: true }).fill('Дарья')
  await page.getByLabel('Электронная почта').fill(`ui-${randomUUID()}@example.com`)
  await page.getByRole('button', { name: 'Получить код' }).click()
  await page.getByLabel('Код из письма').fill('000000')
  await page.getByRole('button', { name: 'Продолжить' }).click()
  await expect(page.getByRole('alert')).toContainText('Неверный код')
  await page.getByLabel('Код из письма').fill('314159')
  await page.getByRole('button', { name: 'Продолжить' }).click()
  await expect(page).toHaveURL(/\/library$/)
  await page.getByRole('link', { name: 'Профиль', exact: true }).click()
  await expect(page.getByLabel('Имя', { exact: true })).toHaveValue('Дарья')
  await page.getByLabel('Имя', { exact: true }).fill('Даша')
  await page.getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Имя сохранено')
  await page.getByRole('button', { name: 'Выйти из аккаунта' }).click()
  await expect(page).toHaveURL(/\/login$/)
  expect(errors).toEqual([])
})

test('каталог, фильтры, пагинация и обложки', async ({ page }) => {
  await login(page)
  await page.screenshot({ path: 'test-results/catalog-desktop.png', fullPage: true })
  await expect(page.locator('.work-card .cover img').first()).toBeVisible()
  expect(
    await page
      .locator('.work-card .cover img')
      .first()
      .evaluate((img) => img.complete && img.naturalWidth > 0),
  ).toBeTruthy()
  const first = await page.locator('.card-title').first().innerText()
  await page.getByRole('button', { name: 'Далее', exact: true }).click()
  await expect(page.locator('.card-title').first()).not.toHaveText(first)
  await page.getByRole('button', { name: 'Фильтры', exact: true }).click()
  await dialog(page).getByRole('button', { name: 'Книга', exact: true }).click()
  await dialog(page).getByRole('button', { name: 'Фантастика', exact: true }).click()
  await dialog(page).getByRole('button', { name: 'Применить' }).click()
  await expect(page).toHaveURL(/types=book/)
  await expect(page.locator('.work-card').first()).toBeVisible()
  const types = await page.locator('.card-meta dd:first-of-type').allTextContents()
  expect(types.every((type) => type === 'Книга')).toBeTruthy()
  await page.getByLabel('Поиск по названию').fill('несуществующеепроизведение123')
  await expect(page.getByRole('heading', { name: 'Ничего не найдено' })).toBeVisible()
  await page.getByRole('button', { name: 'Сбросить поиск' }).click()
  await expect(page.locator('.work-card')).toHaveCount(12)
})

test('библиотека, ручные теги, текст отзыва и удаление', async ({ page }) => {
  await login(page)
  await page.getByLabel('Поиск по названию').fill('Solo Leveling')
  await expect(page.locator('.card-title').first()).toContainText('Solo Leveling')
  await page.locator('.work-card').first().getByRole('button', { name: 'Добавить в библиотеку' }).click()
  await dialog(page).getByRole('combobox', { name: 'Статус', exact: true }).selectOption('completed')
  await dialog(page).getByRole('button', { name: 'Оценка 5', exact: true }).click()
  await dialog(page).getByRole('button', { name: 'Выбрать теги' }).click()
  await dialog(page).getByLabel('Поиск тегов', { exact: true }).fill('умный')
  const tag = dialog(page).locator('.tag-choice').first()
  await tag.getByRole('button').first().click()
  await dialog(page).getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(dialog(page)).toHaveCount(0)
  await page.getByRole('link', { name: 'Моя библиотека', exact: true }).click()
  await expect(page.locator('.work-card')).toHaveCount(1)
  await page.locator('.card-title').click()
  await expect(page.getByRole('heading', { name: 'Мои теги' })).toBeVisible()
  await page.getByRole('button', { name: 'Редактировать отзыв' }).click()
  await dialog(page).getByRole('button', { name: 'Написать отзыв' }).click()
  await dialog(page)
    .getByLabel('Что понравилось', { exact: true })
    .fill('Умный герой и постепенное развитие его способностей')
  await dialog(page)
    .getByLabel('Что не понравилось', { exact: true })
    .fill('Слишком много повторяющихся боёв')
  await dialog(page).getByLabel('Комментарий', { exact: true }).fill('Жду продолжения')
  await dialog(page).getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(page.locator('.review-text')).toContainText('Жду продолжения')
  await expect(page.locator('.analysis-state')).toContainText('ожидает анализа')
  await page.screenshot({ path: 'test-results/detail-desktop.png', fullPage: true })
  await page.getByRole('link', { name: 'Найти похожие' }).click()
  await expect(page.getByRole('heading', { name: 'Похожие произведения' })).toBeVisible()
  await expect(page.locator('.work-card').first()).toBeVisible()
  await page.goBack()
  await page.getByRole('button', { name: 'Удалить из библиотеки' }).click()
  await dialog(page).getByRole('button', { name: 'Удалить', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Добавить в библиотеку' })).toBeVisible()
})

test('личная карточка, загрузка обложки, исправление и удаление', async ({ page }) => {
  await login(page)
  await page.getByRole('link', { name: 'Моя библиотека', exact: true }).click()
  await page.getByRole('button', { name: 'Добавить произведение' }).click()
  await dialog(page).getByLabel('Название *', { exact: true }).fill('Моя личная книга')
  await dialog(page).locator('input[type=file]').setInputFiles(path.resolve('public/miku-shiba.png'))
  await dialog(page).getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(page).toHaveURL(/\/works\/private\//)
  await expect(page.locator('.detail-top .cover img')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Моя личная книга' })).toBeVisible()
  await page.getByRole('button', { name: 'Изменить карточку' }).click()
  await dialog(page).getByLabel('Название *', { exact: true }).fill('Исправленное название')
  await dialog(page).getByLabel('Год', { exact: true }).fill('2024')
  await dialog(page).getByLabel('Страна', { exact: true }).fill('Россия')
  await dialog(page).getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Исправленное название' })).toBeVisible()
  await expect(page.locator('.detail-meta')).toContainText('2024')
  await page.getByRole('button', { name: 'Удалить из библиотеки' }).click()
  await dialog(page).getByRole('button', { name: 'Удалить', exact: true }).click()
  await expect(page).toHaveURL(/\/library$/)
  await expect(page.getByRole('heading', { name: 'В библиотеке пока пусто' })).toBeVisible()
})

test('рекомендации, скрытие, восстановление и исключение библиотеки', async ({ page }) => {
  await login(page)
  await page.getByRole('link', { name: 'Рекомендации', exact: true }).click()
  await expect(page.locator('.work-card')).toHaveCount(12)
  const title = await page.locator('.card-title').first().innerText()
  await page.locator('.work-card').first().getByRole('button', { name: 'Скрыть рекомендацию' }).click()
  await expect(page.locator('.card-title').filter({ hasText: title })).toHaveCount(0)
  await page.getByRole('link', { name: 'Скрытые', exact: true }).click()
  await expect(page.locator('.card-title')).toHaveText(title)
  await page.getByRole('button', { name: 'Вернуть', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Нет скрытых произведений' })).toBeVisible()
  await page.getByRole('link', { name: 'К рекомендациям' }).click()
  await page.locator('.work-card').first().getByRole('button', { name: 'Добавить в библиотеку' }).click()
  await dialog(page).getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(page.locator('.card-title').filter({ hasText: title })).toHaveCount(0)
})

test('истёкший access обновляется один раз без формы входа', async ({ page, context }) => {
  await login(page)
  const cookies = await context.cookies()
  await context.clearCookies()
  await context.addCookies(cookies.filter((cookie) => cookie.name === 'refresh_token'))
  let refreshes = 0
  page.on('request', (request) => {
    if (request.url().endsWith('/auth/refresh')) refreshes++
  })
  await page.reload()
  await expect(page.locator('.work-card')).toHaveCount(12)
  expect(refreshes).toBe(1)
  await context.clearCookies()
  await page.reload()
  await expect(page).toHaveURL(/\/login/)
})

test('сбой сохранения сохраняет введённый отзыв', async ({ page }) => {
  await login(page)
  await page.locator('.work-card').first().getByRole('button', { name: 'Добавить в библиотеку' }).click()
  await dialog(page).getByLabel('Что понравилось', { exact: true }).fill('Дружба героев')
  await page.route('**/api/v1/me/library', (route) =>
    route.request().method() === 'POST'
      ? route.fulfill({ status: 503, json: { error: { message: 'Временная ошибка' } } })
      : route.continue(),
  )
  await dialog(page).getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(dialog(page).getByRole('alert')).toContainText('Временная ошибка')
  await expect(dialog(page).getByLabel('Что понравилось', { exact: true })).toHaveValue('Дружба героев')
  await page.unroute('**/api/v1/me/library')
  await dialog(page).getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(dialog(page)).toHaveCount(0)
})

test('мобильный экран и фильтры без горизонтального скролла', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/login')
  await page.screenshot({ path: 'test-results/login-mobile.png', fullPage: true })
  await login(page)
  await page.screenshot({ path: 'test-results/catalog-mobile.png', fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.getByRole('button', { name: 'Фильтры', exact: true }).click()
  await expect(dialog(page)).toBeVisible()
  await page.screenshot({ path: 'test-results/filters-mobile.png', fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await dialog(page).getByRole('button', { name: 'Применить' }).click()
  await expect(dialog(page)).toHaveCount(0)
})

test('повтор загрузки обложки не создаёт вторую карточку', async ({ page }) => {
  await login(page)
  let creates = 0
  page.on('request', (request) => {
    if (request.url().endsWith('/me/private-works') && request.method() === 'POST') creates++
  })
  await page.route('**/api/v1/me/private-works/*/cover', (route) =>
    route.request().method() === 'PUT'
      ? route.fulfill({ status: 503, json: { error: { message: 'Не удалось загрузить файл' } } })
      : route.continue(),
  )
  await page.getByRole('button', { name: 'Добавить произведение' }).click()
  await dialog(page).getByLabel('Название *', { exact: true }).fill('Обложка со второго раза')
  await dialog(page).locator('input[type=file]').setInputFiles(path.resolve('public/miku-shiba.png'))
  await dialog(page).getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(dialog(page).getByRole('alert')).toContainText('Карточка создана')
  await page.unroute('**/api/v1/me/private-works/*/cover')
  await dialog(page).getByRole('button', { name: 'Повторить загрузку' }).click()
  await expect(page).toHaveURL(/\/works\/private\//)
  await expect(page.locator('.detail-top .cover img')).toBeVisible()
  expect(creates).toBe(1)
})

test('общий лимит текста отзыва проверяется до отправки', async ({ page }) => {
  await login(page)
  await page.locator('.work-card').first().getByRole('button', { name: 'Добавить в библиотеку' }).click()
  await dialog(page).getByLabel('Что понравилось', { exact: true }).fill('а'.repeat(2501))
  await dialog(page).getByLabel('Что не понравилось', { exact: true }).fill('б'.repeat(2501))
  let writes = 0
  page.on('request', (request) => {
    if (request.url().endsWith('/me/library') && request.method() === 'POST') writes++
  })
  await dialog(page).getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(dialog(page).getByRole('alert')).toContainText('5000')
  expect(writes).toBe(0)
  await dialog(page).getByLabel('Что не понравилось', { exact: true }).fill('')
  await dialog(page).getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(dialog(page)).toHaveCount(0)
})

test('одновременные запросы используют один refresh', async ({ page, context }) => {
  await login(page)
  await page.getByRole('link', { name: 'Профиль', exact: true }).click()
  await expect(page.getByLabel('Имя', { exact: true })).toHaveValue('Дарья')
  const cookies = await context.cookies()
  await context.clearCookies()
  await context.addCookies(cookies.filter((cookie) => cookie.name === 'refresh_token'))
  let refreshes = 0
  page.on('request', (request) => {
    if (request.url().endsWith('/auth/refresh')) refreshes++
  })
  const lengths = await page.evaluate(async () => {
    const { api } = await import('/src/api.js')
    const results = await Promise.all([api('/types'), api('/genres'), api('/tags')])
    return results.map((result) => result.items.length)
  })
  expect(lengths.every((length) => length > 0)).toBeTruthy()
  expect(refreshes).toBe(1)
})

test('анализ показывает ошибку, повтор и найденные теги', async ({ page }) => {
  await login(page)
  await page.locator('.work-card').first().getByRole('button', { name: 'Добавить в библиотеку' }).click()
  await dialog(page).getByLabel('Что понравилось', { exact: true }).fill('Дружба героев')
  await dialog(page).getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(dialog(page)).toHaveCount(0)
  let retried = false
  await page.route('**/api/v1/me/library/*/analysis', (route) =>
    route.fulfill({
      json: {
        analysis: { status: retried ? 'done' : 'error', version: 1 },
        effective_source: retried ? 'review' : 'none',
        signals: retried
          ? [
              {
                tag: { id: '00000000-0000-4000-8000-000000000001', name: 'Дружба' },
                value: 1,
                quote: 'Дружба героев',
              },
            ]
          : [],
      },
    }),
  )
  await page.route('**/api/v1/me/library/*/analysis/retry', (route) => {
    retried = true
    return route.fulfill({
      status: 202,
      json: { analysis: { status: 'pending', version: 1 }, effective_source: 'none', signals: [] },
    })
  })
  await page.locator('.card-title').first().click()
  await expect(page.locator('.analysis-state')).toContainText('Не удалось', { timeout: 10000 })
  await page.getByRole('button', { name: 'Повторить', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Теги из отзыва' })).toBeVisible({ timeout: 10000 })
  await expect(page.locator('.signal')).toContainText('Дружба героев')
})
