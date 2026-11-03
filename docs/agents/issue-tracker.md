# Issue tracker: GitHub

Issues и спецификации живут в GitHub Issues репозитория `klawisha012/test`. Все операции через `gh` с явным `-R klawisha012/test`.

- Создать: `gh issue create -R klawisha012/test --title "..." --body-file <файл>`
- Прочитать: `gh issue view <n> -R klawisha012/test --comments`
- Список: `gh issue list -R klawisha012/test --state open --json number,title,body,labels`
- Метки: `gh issue edit <n> --add-label "..."` / `--remove-label "..."`
- Закрыть: `gh issue close <n> --comment "..."`
- Подзадачи: нативные sub-issues (`POST repos/<repo>/issues/<parent>/sub_issues` с `sub_issue_id` — числовой database id).
- Блокировки: нативные зависимости (`POST repos/<repo>/issues/<n>/dependencies/blocked_by` с `issue_id` — database id блокера).

**PR как источник запросов: нет.**

Распределение владельцев: `.agents/workflow/distribution.md`.
