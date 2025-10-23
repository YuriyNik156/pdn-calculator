from fastapi.openapi.utils import get_openapi

def custom_openapi(app):
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="PDN Calculator API",
        version="1.0.0",
        description=(
            "Сервис расчёта показателя долговой нагрузки (ПДН) для физических и юридических лиц.\n\n"
            "### Поддерживаемые сценарии:\n"
            "- **base** — базовый расчёт\n"
            "- **stress** — стресс-тест (-20% доход, +10% платежей)\n"
            "- **target** — рефинансирование (новые платежи)\n\n"
            "### Риск-бенды:\n"
            "| Диапазон | Категория |\n"
            "|-----------|------------|\n"
            "| <50% | LOW |\n"
            "| 50–80% | MID |\n"
            "| >80% | HIGH |\n\n"
            "### Версия формулы: **v1.0**"
        ),
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema