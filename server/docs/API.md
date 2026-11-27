# API v1 для фронтенда

Базовый путь: `/api/v1`.

Авторизация: cookie `access_token`; без входа доступны только `/auth/*`.

## Типы произведений

| `type` | Название |
|---|---|
| anime | Аниме |
| movie | Фильм |
| series | Сериал |
| animated_movie | Мультфильм |
| animated_series | Мультсериал |
| book | Книга |
| light_novel | Ранобэ |
| web_novel | Веб-роман |
| manga | Манга |
| manhwa | Манхва |
| manhua | Маньхуа |
| comic | Комикс |
| visual_novel | Визуальная новелла |
| other | Другое |

## Справочники и значения

Жанры: `GET /genres`. Теги: `GET /tags`.

| Поле | Значения |
|---|---|
| status | planned: В планах; in_progress: В процессе; completed: Завершено; dropped: Брошено |
| rating | целое 1–5 либо null; только личная оценка |
| scope | catalog: общее произведение; private: личное произведение |
| analysis.status | none: нет отзыва; pending: ожидает анализа; running: анализируется; done: готово; error: ошибка анализа |
| effective_source | none: нет признаков; review: из отзыва; manual: ручной выбор; rating: предположение по оценке |
| manual_tags[].value | 1: понравилось; -1: не понравилось; отсутствие элемента: без отметки |
| signals[].value | -1, -0.3, -0.2, 0, 0.2, 0.3, 1; отрицательное / нейтральное / положительное отношение |
| mode в ответе рекомендаций | personal, general |
| basis у похожих | tags, genres, none |
| age_rating общего произведения | 0+, 6+, 12+, 16+, 18+, G, PG, PG-13, R, R+, R18+ либо null |
| age_rating личного произведения | 0+, 6+, 12+, 16+, 18+ либо null |

### Ограничения полей

| Поле | Ограничение |
|---|---|
| email | корректный адрес до 254 символов |
| name | 1–80 символов |
| title | 1–300 символов |
| description | до 10 000 символов или null |
| author | до 1 000 символов или null |
| country | до 100 символов или null |
| year | целое 1–9999 или null |
| liked, disliked, comment | строка или null; суммарно до 5 000 символов |
| q | до 200 символов; пустая строка: без поиска |
| genre_ids | до 26 разных ID |
| manual_tags | до 100 разных тегов |
| tag_ids, exclude_tag_ids | до 30 ID в каждом фильтре |
| обложка | JPEG/PNG/WebP, до 10 МиБ, без анимации; до 8000 px по стороне и до 20 млн пикселей |

### Query-параметры списков

| Параметр | Формат и ограничения |
|---|---|
| q | Строка до 200 символов; поиск по подстроке названия без учёта регистра, у справочников поиск по name |
| limit | Целое 1–100; по умолчанию 20 |
| offset | Целое от 0; по умолчанию 0 |
| types | Повторяемый параметр, до 14 кодов: `types=anime&types=book` |
| genre_ids | Повторяемый параметр, до 26 UUID |
| statuses | Повторяемый параметр, до 4 значений |
| tag_ids, exclude_tag_ids | Повторяемые параметры, до 30 UUID каждый; пересечение списков запрещено |

`types`, `genre_ids`, `statuses`: любое из выбранных значений. `tag_ids`: все выбранные; `exclude_tag_ids`: ни одного. Разные фильтры действуют одновременно.

`total`: число результатов после фильтрации. Следующая страница: `offset + items.length < total`. При сортировке по году или оценке `null` идёт в конце.

Пустая страница, 200:

```json
{
  "items": [],
  "total": 0
}
```

### Ошибка: формат ответа

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Проверьте поля запроса",
    "fields": [
      {
        "path": "body.rating",
        "message": "Оценка должна быть от 1 до 5"
      }
    ],
    "details": {}
  }
}
```

`fields[].path`: поле запроса; `details`: данные конкретной ошибки. Общие статусы: 401: нужен вход; 403 `ORIGIN_FORBIDDEN`: недопустимый Origin изменяющего запроса; 422: неверные параметры; 429 `RATE_LIMITED`: лимит запросов (`details.retry_after`: секунды).

## Поля отзыва

| Поле | Подпись |
|---|---|
| liked | Что понравилось |
| disliked | Что не понравилось |
| comment | Комментарий |

Поля необязательны; по умолчанию `null`. Пустой текст сохраняется как `null`. Для анализа требуется хотя бы одно непустое поле.

Ручные отметки отправляются в `manual_tags`; в ответе возвращаются в `signals` при `effective_source=manual`.

## Вход и профиль

### POST /auth/request-code

Запрос:

```json
{
  "email": "daria@example.com"
}
```

Обязательное поле: `email`.

Ответ 200:

```json
{
  "code_id": "11111111-1111-4111-8111-111111111111",
  "expires_at": "2026-11-25T12:10:00Z",
  "resend_after": 60
}
```

Код действует 10 минут. `resend_after`: секунды до повторной отправки. Новый код отменяет предыдущий. Ошибка: 503 `EMAIL_UNAVAILABLE`.

### POST /auth/verify-code

Запрос:

```json
{
  "code_id": "11111111-1111-4111-8111-111111111111",
  "code": "004219"
}
```

Обязательны `code_id` (UUID), `code` (строка из 6 цифр). Успех устанавливает cookie на 24 часа; первый вход создаёт аккаунт.

| Ошибка | Значение |
|---|---|
| 422 CODE_INVALID | Неверный код; details.attempts_left: оставшиеся попытки или null |
| 410 CODE_EXPIRED | Код истёк |
| 429 CODE_ATTEMPTS_EXCEEDED | Исчерпаны 5 попыток; нужен новый код |

**Ответ 200:**

```json
{
  "user": {
    "id": "33333333-3333-4333-8333-333333333333",
    "email": "daria@example.com",
    "name": "Пользователь"
  },
  "is_new_user": true
}
```

### POST /auth/logout

Без тела. Ответ 204; удаляет cookie. Повтор: 204.

### GET /me

Без параметров.

**Ответ 200:**

```json
{
  "id": "33333333-3333-4333-8333-333333333333",
  "email": "daria@example.com",
  "name": "Дарья"
}
```

### PATCH /me

Запрос:

```json
{
  "name": "Дарья"
}
```

Обязательное поле: `name`.

**Ответ 200:**

```json
{
  "id": "33333333-3333-4333-8333-333333333333",
  "email": "daria@example.com",
  "name": "Дарья"
}
```

## Справочники

### GET /types

Без параметров.

**Ответ 200:**

```json
{
  "items": [
    {
      "code": "anime",
      "name": "Аниме"
    },
    {
      "code": "movie",
      "name": "Фильм"
    }
  ]
}
```

### GET /genres

Query: `q`: необязательная строка, поиск по названию. Без пагинации.

**Ответ 200:**

```json
{
  "items": [
    {
      "id": "9f5573ec-73d0-5cbe-b514-3e050b876955",
      "name": "Экшен"
    },
    {
      "id": "a1ddd24e-b736-5398-a0dc-8c1b8f35587f",
      "name": "Приключения"
    }
  ]
}
```

### GET /tags

Query: `q`, `limit`, `offset` (необязательные). Сортировка по имени.

Запрос: `/api/v1/tags?limit=2&offset=0`.

**Ответ 200:**

```json
{
  "items": [
    {
      "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      "name": "Абсурдный юмор"
    },
    {
      "id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      "name": "Альтернативная история"
    }
  ],
  "total": 132
}
```

## Каталог

### GET /works

Все query-параметры необязательны:

| Параметр | Что передавать |
|---|---|
| q | Поиск по названию |
| types | Один или несколько кодов типов |
| genre_ids | ID жанров |
| tag_ids | ID обязательных тегов |
| exclude_tag_ids | ID исключённых тегов |
| sort | title_asc (по умолчанию), year_desc |
| limit, offset | Пагинация |

Запрос: `/api/v1/works?types=book&types=web_novel&q=пример&sort=year_desc&limit=20&offset=0`.

Ошибки: 422 `FILTER_CONFLICT`: конфликт фильтров; 422 `REFERENCE_NOT_FOUND`: неизвестный ID жанра/тега.

**Ответ 200:**

```json
{
  "items": [
    {
      "id": "44444444-4444-4444-8444-444444444444",
      "scope": "catalog",
      "title": "Пример книги",
      "type": "book",
      "author": "Имя автора",
      "year": 2025,
      "country": null,
      "age_rating": "12+",
      "cover_url": "/api/v1/works/44444444-4444-4444-8444-444444444444/cover",
      "genres": [
        {
          "id": "25c06b67-da07-5dcb-a95b-e8fa436c95b0",
          "name": "Драма"
        }
      ],
      "library": null
    }
  ],
  "total": 1
}
```

### GET /works/{id}

Path: `id`: UUID общего произведения. Без query. `entry=null`, если работа не добавлена. Ошибка: 404 `WORK_NOT_FOUND`.

`adaptations`: другие версии произведения, включая добавленные и скрытые. При отсутствии версий возвращается `[]`.

**Ответ 200:**

```json
{
  "work": {
    "id": "44444444-4444-4444-8444-444444444444",
    "scope": "catalog",
    "title": "Пример книги",
    "type": "book",
    "author": "Имя автора",
    "year": 2025,
    "country": null,
    "age_rating": "12+",
    "cover_url": "/api/v1/works/44444444-4444-4444-8444-444444444444/cover",
    "genres": [
      {
        "id": "25c06b67-da07-5dcb-a95b-e8fa436c95b0",
        "name": "Драма"
      }
    ],
    "description": "Краткое описание произведения.",
    "tags": [
      {
        "id": "88888888-8888-4888-8888-888888888888",
        "name": "Мрачная атмосфера"
      },
      {
        "id": "22222222-2222-4222-8222-222222222222",
        "name": "Умный главный герой"
      }
    ]
  },
  "entry": {
    "id": "66666666-6666-4666-8666-666666666666",
    "status": "completed",
    "rating": 4,
    "liked": "Мне понравился умный главный герой.",
    "disliked": "Мне не понравилась мрачная атмосфера.",
    "comment": null,
    "analysis": {
      "status": "done",
      "version": 1
    },
    "effective_source": "review",
    "signals": [
      {
        "tag": {
          "id": "22222222-2222-4222-8222-222222222222",
          "name": "Умный главный герой"
        },
        "value": 1,
        "quote": "Мне понравился умный главный герой"
      },
      {
        "tag": {
          "id": "88888888-8888-4888-8888-888888888888",
          "name": "Мрачная атмосфера"
        },
        "value": -1,
        "quote": "не понравилась мрачная атмосфера"
      }
    ],
    "created_at": "2026-11-25T12:02:00Z"
  },
  "adaptations": [
    {
      "id": "12121212-1212-4212-8212-121212121212",
      "title": "Пример книги: экранизация",
      "type": "anime",
      "cover_url": "/api/v1/works/12121212-1212-4212-8212-121212121212/cover"
    }
  ]
}
```

### GET /works/{id}/cover

Path: `id`: UUID общего произведения.

Ответ 200: `Content-Type: image/webp`, бинарное изображение. 404: обложка или произведение отсутствует.

## Библиотека

### GET /me/library

Все query-параметры необязательны:

| Параметр | Что передавать |
|---|---|
| q | Поиск по названию |
| types | Коды типов |
| genre_ids | ID жанров |
| statuses | planned, in_progress, completed, dropped; множественный выбор |
| scope | catalog или private; без параметра оба вида |
| sort | added_desc (по умолчанию), title_asc, rating_desc |
| limit, offset | Пагинация |

**Ответ 200:**

```json
{
  "items": [
    {
      "id": "99999999-9999-4999-8999-999999999999",
      "status": "in_progress",
      "rating": 5,
      "liked": null,
      "disliked": null,
      "comment": null,
      "analysis": {
        "status": "none",
        "version": 0
      },
      "effective_source": "manual",
      "signals": [
        {
          "tag": {
            "id": "22222222-2222-4222-8222-222222222222",
            "name": "Умный главный герой"
          },
          "value": 1,
          "quote": null
        }
      ],
      "created_at": "2026-11-25T12:03:00Z",
      "work": {
        "id": "55555555-5555-4555-8555-555555555555",
        "scope": "private",
        "title": "Пример личной книги",
        "type": "book",
        "author": "Другой автор",
        "year": 2024,
        "country": null,
        "age_rating": "12+",
        "cover_url": "/api/v1/me/private-works/55555555-5555-4555-8555-555555555555/cover?v=8dd51d",
        "genres": [
          {
            "id": "25c06b67-da07-5dcb-a95b-e8fa436c95b0",
            "name": "Драма"
          }
        ]
      }
    },
    {
      "id": "66666666-6666-4666-8666-666666666666",
      "status": "completed",
      "rating": 4,
      "liked": "Мне понравился умный главный герой.",
      "disliked": "Мне не понравилась мрачная атмосфера.",
      "comment": null,
      "analysis": {
        "status": "done",
        "version": 1
      },
      "effective_source": "review",
      "signals": [
        {
          "tag": {
            "id": "22222222-2222-4222-8222-222222222222",
            "name": "Умный главный герой"
          },
          "value": 1,
          "quote": "Мне понравился умный главный герой"
        },
        {
          "tag": {
            "id": "88888888-8888-4888-8888-888888888888",
            "name": "Мрачная атмосфера"
          },
          "value": -1,
          "quote": "не понравилась мрачная атмосфера"
        }
      ],
      "created_at": "2026-11-25T12:02:00Z",
      "work": {
        "id": "44444444-4444-4444-8444-444444444444",
        "scope": "catalog",
        "title": "Пример книги",
        "type": "book",
        "author": "Имя автора",
        "year": 2025,
        "country": null,
        "age_rating": "12+",
        "cover_url": "/api/v1/works/44444444-4444-4444-8444-444444444444/cover",
        "genres": [
          {
            "id": "25c06b67-da07-5dcb-a95b-e8fa436c95b0",
            "name": "Драма"
          }
        ]
      }
    }
  ],
  "total": 2
}
```

### POST /me/library

Запрос:

```json
{
  "work_id": "44444444-4444-4444-8444-444444444444",
  "status": "planned",
  "rating": null,
  "liked": null,
  "disliked": null,
  "comment": null,
  "manual_tags": []
}
```

Обязателен `work_id` (UUID). Остальные поля необязательны; в примере: значения по умолчанию.

Ошибки: 409 `ALREADY_IN_LIBRARY` (`details.library_id`: существующая запись); 404 `WORK_NOT_FOUND`; 422 `FEEDBACK_CONFLICT`: заполнено любое из liked/disliked/comment вместе с manual_tags.

**Ответ 201:**

```json
{
  "id": "66666666-6666-4666-8666-666666666666",
  "status": "planned",
  "rating": null,
  "liked": null,
  "disliked": null,
  "comment": null,
  "analysis": {
    "status": "none",
    "version": 0
  },
  "effective_source": "none",
  "signals": [],
  "created_at": "2026-11-25T12:02:00Z",
  "work": {
    "id": "44444444-4444-4444-8444-444444444444",
    "scope": "catalog",
    "title": "Пример книги",
    "type": "book",
    "author": "Имя автора",
    "year": 2025,
    "country": null,
    "age_rating": "12+",
    "cover_url": "/api/v1/works/44444444-4444-4444-8444-444444444444/cover",
    "genres": [
      {
        "id": "25c06b67-da07-5dcb-a95b-e8fa436c95b0",
        "name": "Драма"
      }
    ]
  }
}
```

### GET /me/library/{id}

Path: `id`: UUID записи библиотеки. Без query. Ошибка: 404 `LIBRARY_ENTRY_NOT_FOUND`.

**Ответ 200:**

```json
{
  "id": "66666666-6666-4666-8666-666666666666",
  "status": "completed",
  "rating": 4,
  "liked": "Мне понравился умный главный герой.",
  "disliked": "Мне не понравилась мрачная атмосфера.",
  "comment": null,
  "analysis": {
    "status": "done",
    "version": 1
  },
  "effective_source": "review",
  "signals": [
    {
      "tag": {
        "id": "22222222-2222-4222-8222-222222222222",
        "name": "Умный главный герой"
      },
      "value": 1,
      "quote": "Мне понравился умный главный герой"
    },
    {
      "tag": {
        "id": "88888888-8888-4888-8888-888888888888",
        "name": "Мрачная атмосфера"
      },
      "value": -1,
      "quote": "не понравилась мрачная атмосфера"
    }
  ],
  "created_at": "2026-11-25T12:02:00Z",
  "work": {
    "id": "44444444-4444-4444-8444-444444444444",
    "scope": "catalog",
    "title": "Пример книги",
    "type": "book",
    "author": "Имя автора",
    "year": 2025,
    "country": null,
    "age_rating": "12+",
    "cover_url": "/api/v1/works/44444444-4444-4444-8444-444444444444/cover",
    "genres": [
      {
        "id": "25c06b67-da07-5dcb-a95b-e8fa436c95b0",
        "name": "Драма"
      }
    ]
  }
}
```

### PATCH /me/library/{id}

Path: `id`: UUID записи библиотеки. JSON: `status`, `rating`, `liked`, `disliked`, `comment`, `manual_tags` (хотя бы одно поле). Остальные поля не меняются; null очищает rating или отдельное текстовое поле.

Изменение статуса:

```json
{
  "status": "completed"
}
```

Установка оценки:

```json
{
  "rating": 4
}
```

Очистка оценки:

```json
{
  "rating": null
}
```

Ручные признаки без текста:

```json
{
  "liked": null,
  "disliked": null,
  "comment": null,
  "manual_tags": [
    {
      "tag_id": "22222222-2222-4222-8222-222222222222",
      "value": 1
    }
  ]
}
```

Замена ручных отметок отзывом:

```json
{
  "liked": "Мне понравился умный главный герой.",
  "disliked": null,
  "comment": "Хочу прочитать продолжение.",
  "manual_tags": []
}
```

- Текст и непустой `manual_tags` несовместимы: 422 `FEEDBACK_CONFLICT`. При смене режима требуется очистка прежних полей в том же PATCH.
- `manual_tags` заменяется целиком; `[]` очищает отметки. Доступен любой тег из `GET /tags`.
- Новый текст: `analysis.status=pending`; весь текст очищен: `none`. Изменение только оценки или статуса не запускает анализ.
- Ошибки: 422 `REFERENCE_NOT_FOUND`: неизвестный тег; 404 `LIBRARY_ENTRY_NOT_FOUND`.

**Ответ после примера с новым отзывом 200:**

```json
{
  "id": "66666666-6666-4666-8666-666666666666",
  "status": "completed",
  "rating": 4,
  "liked": "Мне понравился умный главный герой.",
  "disliked": null,
  "comment": "Хочу прочитать продолжение.",
  "analysis": {
    "status": "pending",
    "version": 2
  },
  "effective_source": "none",
  "signals": [],
  "created_at": "2026-11-25T12:02:00Z",
  "work": {
    "id": "44444444-4444-4444-8444-444444444444",
    "scope": "catalog",
    "title": "Пример книги",
    "type": "book",
    "author": "Имя автора",
    "year": 2025,
    "country": null,
    "age_rating": "12+",
    "cover_url": "/api/v1/works/44444444-4444-4444-8444-444444444444/cover",
    "genres": [
      {
        "id": "25c06b67-da07-5dcb-a95b-e8fa436c95b0",
        "name": "Драма"
      }
    ]
  }
}
```

**Ответ после примера с ручным выбором 200:**

```json
{
  "id": "66666666-6666-4666-8666-666666666666",
  "status": "completed",
  "rating": 4,
  "liked": null,
  "disliked": null,
  "comment": null,
  "analysis": {
    "status": "none",
    "version": 2
  },
  "effective_source": "manual",
  "signals": [
    {
      "tag": {
        "id": "22222222-2222-4222-8222-222222222222",
        "name": "Умный главный герой"
      },
      "value": 1,
      "quote": null
    }
  ],
  "created_at": "2026-11-25T12:02:00Z",
  "work": {
    "id": "44444444-4444-4444-8444-444444444444",
    "scope": "catalog",
    "title": "Пример книги",
    "type": "book",
    "author": "Имя автора",
    "year": 2025,
    "country": null,
    "age_rating": "12+",
    "cover_url": "/api/v1/works/44444444-4444-4444-8444-444444444444/cover",
    "genres": [
      {
        "id": "25c06b67-da07-5dcb-a95b-e8fa436c95b0",
        "name": "Драма"
      }
    ]
  }
}
```

### DELETE /me/library/{id}

Path: `id`: UUID записи библиотеки. Без тела. Удаляет запись и впечатления; для личной работы удаляет также карточку и обложку.

Ответ 204, без тела. Ошибка: 404 `LIBRARY_ENTRY_NOT_FOUND`.

## Анализ отзыва

### GET /me/library/{id}/analysis

Path: `id`: UUID записи библиотеки. Без query.

Ответ 200, анализ ожидается:

```json
{
  "analysis": {
    "status": "pending",
    "version": 1
  },
  "effective_source": "none",
  "signals": []
}
```

`version`: только для чтения. При `done` список `signals` может быть пустым. Ошибка анализа: HTTP 200, `analysis.status=error`. Запись не найдена: 404 `LIBRARY_ENTRY_NOT_FOUND`.

**Ответ после успешного анализа 200:**

```json
{
  "analysis": {
    "status": "done",
    "version": 1
  },
  "effective_source": "review",
  "signals": [
    {
      "tag": {
        "id": "22222222-2222-4222-8222-222222222222",
        "name": "Умный главный герой"
      },
      "value": 1,
      "quote": "Мне понравился умный главный герой"
    },
    {
      "tag": {
        "id": "88888888-8888-4888-8888-888888888888",
        "name": "Мрачная атмосфера"
      },
      "value": -1,
      "quote": "не понравилась мрачная атмосфера"
    }
  ]
}
```

**Ответ при ошибке анализа 200:**

```json
{
  "analysis": {
    "status": "error",
    "version": 1
  },
  "effective_source": "none",
  "signals": []
}
```

### POST /me/library/{id}/analysis/retry

Path: `id`: UUID записи библиотеки. Без тела. Повтор доступен только при `analysis.status=error`. Ошибки: 409 `ANALYSIS_NOT_RETRYABLE`; 404 `LIBRARY_ENTRY_NOT_FOUND`.

**Ответ 202:**

```json
{
  "analysis": {
    "status": "pending",
    "version": 2
  },
  "effective_source": "none",
  "signals": []
}
```

## Личные произведения

### POST /me/private-works

Обязательны только `title` и `type`. Минимальный запрос:

```json
{
  "title": "Название",
  "type": "book"
}
```

Все допустимые поля (необязательные показаны со значениями по умолчанию):

```json
{
  "title": "Название",
  "type": "book",
  "description": null,
  "author": null,
  "year": null,
  "country": null,
  "age_rating": null,
  "genre_ids": [],
  "entry": {
    "status": "planned",
    "rating": null,
    "liked": null,
    "disliked": null,
    "comment": null,
    "manual_tags": []
  }
}
```

Все поля кроме `title` и `type` необязательны, включая поля `entry`. Без `entry`: статус `planned`, без оценки и отзыва. `entry={}` допустим; `entry=null` запрещён. Обложка загружается отдельно: `PUT /me/private-works/{id}/cover`.

В ответе `id`: запись библиотеки, `work.id`: личное произведение. Текст и ручные теги в `entry` несовместимы: 422 `FEEDBACK_CONFLICT`.

**Ответ 201:**

```json
{
  "id": "99999999-9999-4999-8999-999999999999",
  "status": "planned",
  "rating": null,
  "liked": null,
  "disliked": null,
  "comment": null,
  "analysis": {
    "status": "none",
    "version": 0
  },
  "effective_source": "none",
  "signals": [],
  "created_at": "2026-11-25T12:03:00Z",
  "work": {
    "id": "55555555-5555-4555-8555-555555555555",
    "scope": "private",
    "title": "Название",
    "type": "book",
    "author": null,
    "year": null,
    "country": null,
    "age_rating": null,
    "cover_url": null,
    "genres": []
  }
}
```

### GET /me/private-works/{id}

Path: `id`: UUID личного произведения. Без query. Ошибка: 404 `PRIVATE_WORK_NOT_FOUND`.

**Ответ 200:**

```json
{
  "work": {
    "id": "55555555-5555-4555-8555-555555555555",
    "scope": "private",
    "title": "Пример личной книги",
    "type": "book",
    "author": "Другой автор",
    "year": 2024,
    "country": null,
    "age_rating": "12+",
    "cover_url": "/api/v1/me/private-works/55555555-5555-4555-8555-555555555555/cover?v=8dd51d",
    "genres": [
      {
        "id": "25c06b67-da07-5dcb-a95b-e8fa436c95b0",
        "name": "Драма"
      }
    ],
    "description": "Описание, которое ввёл пользователь.",
    "tags": []
  },
  "entry": {
    "id": "99999999-9999-4999-8999-999999999999",
    "status": "in_progress",
    "rating": 5,
    "liked": null,
    "disliked": null,
    "comment": null,
    "analysis": {
      "status": "none",
      "version": 0
    },
    "effective_source": "manual",
    "signals": [
      {
        "tag": {
          "id": "22222222-2222-4222-8222-222222222222",
          "name": "Умный главный герой"
        },
        "value": 1,
        "quote": null
      }
    ],
    "created_at": "2026-11-25T12:03:00Z"
  }
}
```

### PATCH /me/private-works/{id}

Path: `id`: UUID личного произведения. JSON: `title`, `type`, `description`, `author`, `year`, `country`, `age_rating`, `genre_ids` (хотя бы одно поле). null очищает nullable-поле; genre_ids заменяется целиком, [] снимает жанры.

Запрос:

```json
{
  "title": "Новое название",
  "type": "other",
  "author": "Имя создателя"
}
```

Ошибка: 404 `PRIVATE_WORK_NOT_FOUND`. Впечатления меняются через PATCH /me/library/{id}.

**Ответ 200:**

```json
{
  "work": {
    "id": "55555555-5555-4555-8555-555555555555",
    "scope": "private",
    "title": "Новое название",
    "type": "other",
    "author": "Имя создателя",
    "year": 2024,
    "country": null,
    "age_rating": "12+",
    "cover_url": "/api/v1/me/private-works/55555555-5555-4555-8555-555555555555/cover?v=8dd51d",
    "genres": [
      {
        "id": "25c06b67-da07-5dcb-a95b-e8fa436c95b0",
        "name": "Драма"
      }
    ],
    "description": "Описание, которое ввёл пользователь.",
    "tags": []
  },
  "entry": {
    "id": "99999999-9999-4999-8999-999999999999",
    "status": "in_progress",
    "rating": 5,
    "liked": null,
    "disliked": null,
    "comment": null,
    "analysis": {
      "status": "none",
      "version": 0
    },
    "effective_source": "manual",
    "signals": [
      {
        "tag": {
          "id": "22222222-2222-4222-8222-222222222222",
          "name": "Умный главный герой"
        },
        "value": 1,
        "quote": null
      }
    ],
    "created_at": "2026-11-25T12:03:00Z"
  }
}
```

### PUT /me/private-works/{id}/cover

Path: `id`: UUID личного произведения. Тело: `multipart/form-data`.

| Поле | Тип | Обязательное |
|---|---|---|
| file | Файл JPEG/PNG/WebP; ограничения выше | Да |

Ответ 200:

```json
{
  "cover_url": "/api/v1/me/private-works/55555555-5555-4555-8555-555555555555/cover?v=8dd51d"
}
```

Ошибки: 413: превышен размер; 415: неподдерживаемый формат; 422: повреждённое изображение или недопустимые размеры; 404 `PRIVATE_WORK_NOT_FOUND`.

### GET /me/private-works/{id}/cover

Path: `id`: UUID личного произведения.

Ответ 200: `Content-Type: image/webp`, бинарное изображение. 404: карточка или обложка недоступна.

### DELETE /me/private-works/{id}/cover

Path: `id`: UUID личного произведения. Без тела.

Ответ 204, без тела; повтор тоже 204. Ошибка: 404 `PRIVATE_WORK_NOT_FOUND`.

## Рекомендации

### GET /me/recommendations

Все query-параметры необязательны:

| Параметр | Значения |
|---|---|
| q | Поиск по названию |
| types | Коды типов |
| genre_ids | UUID жанров |
| tag_ids | UUID обязательных тегов |
| exclude_tag_ids | UUID исключённых тегов |
| limit, offset | Пагинация |
| sort | relevance (по умолчанию), title_asc, year_desc |

Пример пустого ответа 200:

```json
{
  "items": [],
  "total": 0,
  "mode": "personal"
}
```

`mode`: `personal`: персональные рекомендации; `general`: общая подборка без положительных предпочтений. Пустая страница не меняет режим. Библиотека и скрытые работы исключены.

`reason.text`: объяснение; `reason.source_work`: источник или `null`.

Ошибка: 422 `FILTER_CONFLICT`.

**Ответ с персональной рекомендацией 200:**

```json
{
  "items": [
    {
      "work": {
        "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "scope": "catalog",
        "title": "Пример другого произведения",
        "type": "book",
        "author": "Имя автора",
        "year": 2025,
        "country": null,
        "age_rating": "12+",
        "cover_url": "/api/v1/works/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/cover",
        "genres": [
          {
            "id": "25c06b67-da07-5dcb-a95b-e8fa436c95b0",
            "name": "Драма"
          }
        ]
      },
      "reason": {
        "text": "Вам понравился умный главный герой в «Пример книги».",
        "source_work": {
          "id": "44444444-4444-4444-8444-444444444444",
          "scope": "catalog",
          "title": "Пример книги"
        }
      }
    }
  ],
  "total": 1,
  "mode": "personal"
}
```

**Ответ с общей подборкой 200:**

```json
{
  "items": [
    {
      "work": {
        "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "scope": "catalog",
        "title": "Пример другого произведения",
        "type": "book",
        "author": "Имя автора",
        "year": 2025,
        "country": null,
        "age_rating": "12+",
        "cover_url": "/api/v1/works/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/cover",
        "genres": [
          {
            "id": "25c06b67-da07-5dcb-a95b-e8fa436c95b0",
            "name": "Драма"
          }
        ]
      },
      "reason": {
        "text": "Общая подборка",
        "source_work": null
      }
    }
  ],
  "total": 1,
  "mode": "general"
}
```

### PUT /me/hidden/{work_id}

Path: `work_id`: UUID общего произведения. Без тела. Скрывает из рекомендаций и похожих.

Ответ 204, без тела; повтор тоже 204. Ошибка: 404 `WORK_NOT_FOUND`.

### DELETE /me/hidden/{work_id}

Path: `work_id`: UUID общего произведения. Без тела. Снимает скрытие.

Ответ 204, без тела; повтор тоже 204. Ошибка: 404 `WORK_NOT_FOUND`.

### GET /me/hidden

Query: `limit`, `offset` (необязательные). Сортировка по названию.

**Ответ 200:**

```json
{
  "items": [
    {
      "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      "scope": "catalog",
      "title": "Пример другого произведения",
      "type": "book",
      "author": "Имя автора",
      "year": 2025,
      "country": null,
      "age_rating": "12+",
      "cover_url": "/api/v1/works/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/cover",
      "genres": [
        {
          "id": "25c06b67-da07-5dcb-a95b-e8fa436c95b0",
          "name": "Драма"
        }
      ],
      "library": null
    }
  ],
  "total": 1
}
```

## Найти похожие

### GET /works/{id}/similar

Path: `id`: UUID общего произведения. Query: `q`, `types`, `genre_ids`, `limit`, `offset` (необязательные). Сортировка по похожести.

Пример пустого ответа 200:

```json
{
  "items": [],
  "total": 0,
  "basis": "genres"
}
```

| basis | Значение |
|---|---|
| tags | По тегам |
| genres | По жанрам |
| none | Нет данных для поиска |

`basis`: `tags`: по тегам; `genres`: по жанрам; `none`: нет данных. Источник, библиотека и скрытые исключены. Ошибка: 404 `WORK_NOT_FOUND`.

Запрос: `/api/v1/works/dddddddd-dddd-4ddd-8ddd-dddddddddddd/similar`.

**Ответ с похожим произведением 200:**

```json
{
  "items": [
    {
      "work": {
        "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "scope": "catalog",
        "title": "Пример другого произведения",
        "type": "book",
        "author": "Имя автора",
        "year": 2025,
        "country": null,
        "age_rating": "12+",
        "cover_url": "/api/v1/works/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/cover",
        "genres": [
          {
            "id": "25c06b67-da07-5dcb-a95b-e8fa436c95b0",
            "name": "Драма"
          }
        ]
      },
      "reason": {
        "text": "Похожие жанры с «Книга без тегов»: Драма."
      }
    }
  ],
  "total": 1,
  "basis": "genres"
}
```

**Ответ при отсутствии данных для поиска 200:**

```json
{
  "items": [],
  "total": 0,
  "basis": "none"
}
```

### GET /me/private-works/{id}/similar

Path: `id`: UUID личного произведения. Query: `q`, `types`, `genre_ids`, `limit`, `offset` (необязательные).

Подбор из каталога по положительным признакам записи, при отсутствии признаков: по жанрам. Сортировка по похожести. Библиотека и скрытые исключены. Ошибка: 404 `PRIVATE_WORK_NOT_FOUND`.

**Ответ 200:**

```json
{
  "items": [
    {
      "work": {
        "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "scope": "catalog",
        "title": "Пример другого произведения",
        "type": "book",
        "author": "Имя автора",
        "year": 2025,
        "country": null,
        "age_rating": "12+",
        "cover_url": "/api/v1/works/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/cover",
        "genres": [
          {
            "id": "25c06b67-da07-5dcb-a95b-e8fa436c95b0",
            "name": "Драма"
          }
        ]
      },
      "reason": {
        "text": "Похожие признаки с «Пример личной книги»: Умный главный герой."
      }
    }
  ],
  "total": 1,
  "basis": "tags"
}
```

## Следующая версия

Администратор, заявки, влияние отзывов на теги произведений не входят в v1.
