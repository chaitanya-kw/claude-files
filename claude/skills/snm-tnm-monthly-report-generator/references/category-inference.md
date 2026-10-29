# Category Inference Guide

There are two independent category systems. Use the Support rules for tasks with `type = Support`,
and the Maintenance rules for tasks with `type = Maintenance`. If `type` itself isn't stated, infer
it first (Maintenance = routine/scheduled upkeep; Support = reactive fix/change work), then apply
the matching category rules below.

---

## Support categories

Apply the **first matching rule** in order.

| If the description mentions… | Infer category |
|---|---|
| broken, error, crash, not working, stopped working, disappeared, wrong, incorrect, missing (feature/element that existed before), showing incorrectly, displaying incorrectly, code appearing on site, erroneous | **Functional Bugs** |
| slow, timeout, load time, performance, memory, cache | **Performance Issues** |
| vulnerability, security, SSL, certificate, exploit, hack, spam, malware, permissions leak | **Security Issues** |
| text, copy, content, image, photo, menu item, price, translation, wording, updated to say, changed to show, typo, spelling | **Content Changes** |
| added, new feature, new section, new page, new button, new banner, enhancement, improvement, upgraded, migrated, pipeline, deploy, rebuilt, restructured | **Enhancement** |
| API, webhook, integration, sync, connection to, third-party, plugin broke, feed, import, export failing | **Integration Error** |

**Fallback:**
1. Default to **Enhancement** for anything that sounds like new work or improvements.
2. Default to **Functional Bugs** for anything that sounds like fixing something broken.
3. If still ambiguous, **ask the user** before generating the report.

---

## Maintenance categories

Apply the **first matching rule** in order.

| If the description mentions… | Infer category |
|---|---|
| core update, WordPress core, Node upgrade, framework update, CMS update, platform update, PHP version, runtime update | **Core Updates** |
| plugin update, package update, dependency update, npm update, composer update, library update, module update | **Plugin/Package Updates** |
| security scan, vulnerability scan, malware scan, penetration test, security audit | **Security Scan** |
| uptime, downtime, uptime monitor, server availability, ping check, outage | **Uptime Scan** |
| accessibility, WCAG, a11y, screen reader, contrast check, alt text audit | **Accessibility Scan** |

**Fallback:** if no rule matches clearly, **ask the user** — do not guess a maintenance category on a low-confidence match, since it directly determines which scan/category rows appear in the Maintenance Overview.

---

## Asking the user

When asking, present the inferred guess alongside the question:

> I couldn't confidently determine the category for this task:
> _"{{TASK_DESCRIPTION}}"_
> My best guess is **{{INFERRED}}** — does that work, or should it be something else?
> (Support options: Functional Bugs / Performance Issues / Security Issues / Content Changes / Enhancement / Integration Error)
> (Maintenance options: Core Updates / Plugin/Package Updates / Security Scan / Uptime Scan / Accessibility Scan)
