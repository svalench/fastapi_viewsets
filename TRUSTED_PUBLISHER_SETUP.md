# Настройка Trusted Publishing для PyPI

## Проблема

Если вы получаете ошибку:
```
Token request failed: the server refused the request for the following reasons:
* `invalid-publisher`: valid token, but no corresponding publisher
```

Это означает, что Trusted Publisher не настроен в PyPI или настройки не совпадают.

## Диагностика по логам

Сверьтесь с логами failed job. Важные claims:

| Claim | Ожидаемое значение | Что проверить |
|-------|-------------------|---------------|
| `repository` | `svalench/fastapi_viewsets` | Должен совпадать с owner/repo на GitHub |
| `workflow_ref` | `.../.github/workflows/release.yml@...` | Должен совпадать с путём к workflow |
| `environment` | `pypi` | В `release.yml` задан environment `pypi` |

Если `workflow_ref` указывает на `release.yml`, а в PyPI настроен `publish.yml` — это и есть причина ошибки.

## Решение 1: Настройка Trusted Publisher в PyPI (Рекомендуется)

### Шаги настройки:

1. **Войдите в PyPI**:
   - Перейдите на https://pypi.org/manage/account/
   - Войдите в свой аккаунт

2. **Перейдите в раздел Trusted Publishing**:
   - В меню слева выберите "Publishing" → "Trusted publishers"
   - Или перейдите напрямую: https://pypi.org/manage/account/publishing/

3. **Добавьте новый Trusted Publisher**:
   - Нажмите "Add a new pending publisher"
   - Заполните форму:
     - **PyPI project name**: `fastapi-viewsets` (или ваше имя пакета)
     - **Publisher type**: `GitHub`
     - **Owner**: `svalench` (ваш GitHub username)
     - **Repository name**: `fastapi_viewsets` (имя репозитория)
     - **Workflow filename**: `.github/workflows/release.yml` ⚠️ (именно `release.yml`, не `publish.yml`)
     - **Environment name**: `pypi` (в `release.yml` используется environment `pypi`)

4. **Сохраните настройки**:
   - Нажмите "Add"
   - Publisher будет добавлен в статус "Pending"

5. **Активируйте publisher**:
   - Запушьте тег (например, `git push origin v1.3.0`)
   - Workflow `release.yml` запустится, и publisher автоматически активируется при первом успешном обмене токенами

### Важные моменты:

- **Workflow filename** должен точно совпадать: `.github/workflows/release.yml`
- **Repository name** должен совпадать с именем репозитория на GitHub (без префикса username/)
- **Owner** должен совпадать с владельцем репозитория на GitHub
- **Environment name** обязателен: введите `pypi` (оставить пустым не получится — в workflow environment задан явно)

## Решение 2: Использование API токена (Быстрое решение)

Если Trusted Publishing настроить сейчас нет возможности, используйте API токен:

### Шаги:

1. **Создайте API токен в PyPI**:
   - Перейдите на https://pypi.org/manage/account/token/
   - Нажмите "Add API token"
   - Введите имя токена (например, "GitHub Actions")
   - Выберите scope: "Entire account" или "Project: fastapi-viewsets"
   - Нажмите "Add token"
   - **ВАЖНО**: Скопируйте токен сразу (он показывается только один раз!)

2. **Добавьте токен в GitHub Secrets**:
   - Перейдите в ваш репозиторий на GitHub
   - Settings → Secrets and variables → Actions
   - Нажмите "New repository secret"
   - Name: `PYPI_API_TOKEN`
   - Value: вставьте скопированный токен
   - Нажмите "Add secret"

3. **Переключите workflow на fallback**:
   - Settings → Secrets and variables → Actions → Variables
   - Нажмите "New repository variable"
   - Name: `USE_PYPI_TOKEN`
   - Value: `true`
   - Нажмите "Add variable"

   Workflow `release.yml` увидит `USE_PYPI_TOKEN=true` и будет использовать `PYPI_API_TOKEN` вместо Trusted Publishing.

## Проверка настройки

После настройки Trusted Publisher, проверьте claims:

- `repository`: `svalench/fastapi_viewsets` ✅
- `repository_owner`: `svalench` ✅
- `workflow_ref`: `svalench/fastapi_viewsets/.github/workflows/release.yml@refs/tags/v1.3.0` ✅
- `environment`: `pypi` ✅

Эти значения должны совпадать с настройками в PyPI.

## Дополнительная информация

- [Документация PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
- [Troubleshooting Guide](https://docs.pypi.org/trusted-publishers/troubleshooting/)
