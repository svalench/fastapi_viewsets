# fastapi-viewsets 1.5.3

This patch restores validation guarantees for PATCH requests. Generated partial
schemas now retain field validators and configuration as well as Field constraints,
aliases and annotations. Fields may be omitted; explicit null is accepted only
when the original field is nullable. Full-model validators are not run on incomplete PATCH bodies; applications that
need cross-field invariants must validate the merged record before committing it.

Creation honors database defaults in SQLAlchemy and Peewee. Missing-field errors
retain their useful message, and Peewee/Tortoise update constraint failures return
HTTP 409 without SQL or submitted values in the response.

Release version input is validated outside the shell, and publishing workflows
share a concurrency group. Existing token/OIDC configuration is unchanged.
