# Настройка Trusted Publishing для PyPI

## Проблема

Если вы получаете ошибку:
```
Token request failed: the server refused the request for the following reasons:
* `invalid-publisher`: valid token, but no corresponding publisher
```

Это означает, что Trusted Publisher не настроен в PyPI или настройки не совпадают.

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
     - **Workflow filename**: `.github/workflows/publish.yml` (путь к workflow файлу)
     - **Environment name**: оставьте пустым (если не используете environments)

4. **Сохраните настройки**:
   - Нажмите "Add"
   - Publisher будет добавлен в статус "Pending"

5. **Активируйте publisher**:
   - После первого успешного запуска workflow publisher автоматически активируется
   - Или вы можете активировать его вручную в PyPI

### Важные моменты:

- **Workflow filename** должен точно совпадать с путем к файлу в репозитории
- **Repository name** должен совпадать с именем репозитория на GitHub (без префикса username/)
- **Owner** должен совпадать с владельцем репозитория на GitHub

## Решение 2: Использование API токена (Быстрое решение)

Если вы не хотите настраивать Trusted Publishing, используйте API токен:

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

3. **Используйте workflow с токеном**:
   - Workflow автоматически определит наличие токена и использует его
   - Или используйте `publish-manual.yml` для ручной публикации

## Проверка настройки

После настройки Trusted Publisher, проверьте claims:

- `repository`: `svalench/fastapi_viewsets` ✅
- `repository_owner`: `svalench` ✅
- `workflow_ref`: `svalench/fastapi_viewsets/.github/workflows/publish.yml@refs/tags/1.0.1` ✅

Эти значения должны совпадать с настройками в PyPI.

## Дополнительная информация

- [Документация PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
- [Troubleshooting Guide](https://docs.pypi.org/trusted-publishers/troubleshooting/)

