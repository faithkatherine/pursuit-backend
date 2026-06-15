---
description: "Add a new Django model to the Pursuit backend"
---

Add a new model named ${input:modelName:e.g. EventBooking}
to the ${input:appName:e.g. events} app.

Steps in order:

1. Read apps/${input:appName}/models.py before writing — extend existing patterns
2. Add model to apps/${input:appName}/models.py
3. Run: python manage.py makemigrations ${input:appName}
4. Verify migration is reversible — add reverse_code if data migration
5. Register model in apps/${input:appName}/admin.py
6. Add to seed script if needed for test scenarios

Model requirements:

- Inherit from base model in apps/core/models.py if one exists
- All FK fields use select_related in resolvers — document this in a comment
- If model has a location_tag field: normalise to lowercase on save()
- If model is an EditorsPick-style editorial model: curator_note must be NOT NULL

Migration requirements:

- Data migrations must be wrapped in a transaction
- Include reverse_code — approximate reverse is acceptable, add comment explaining tradeoff
- Never use RunPython without a reverse function

Admin requirements:

- list_display: at minimum id, main identifier field, created_at
- search_fields on any text fields users will search
- list_filter on category/status/date fields
- raw_id_fields on any FK that could have large querysets (e.g. event FK)

Do NOT:

- Skip admin registration
- Use RunPython without reverse_code
- Add fields without migrations
