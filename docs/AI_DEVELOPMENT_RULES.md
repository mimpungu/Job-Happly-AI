# Happly AI — AI Development Rules

**Version:** 1.0  
**Status:** Mandatory  
**Purpose:** Define the rules and working standards that every AI coding agent must follow when developing Happly AI.

---

## 1. General Principles

You are contributing to **Happly AI**, an AI-powered career companion designed to help users find relevant job opportunities, optimize their resumes, generate tailored cover letters, manage applications, and prepare for interviews.

Your mission is to build a reliable, secure, maintainable, scalable, and production-ready application.

The following principles are mandatory:

- Quality over speed.
- Simplicity over unnecessary complexity.
- Reusable code over duplication.
- Explicit decisions over hidden assumptions.
- Real implementations over mock functionality.
- Security and privacy by design.
- Automated testing wherever practical.
- Consistency with the existing architecture.

Never introduce unnecessary complexity or technologies without a clear justification.

## 2. Documentation Is the Source of Truth

Before performing any development task, read and follow the project documentation:

- `docs/HAPPLY_AI_MASTER_SPEC.md`
- `docs/HAPPLY_AI_MASTER_BACKLOG.md`
- `docs/AI_DEVELOPMENT_RULES.md`

These documents define the product vision, architecture, features, technical constraints, development priorities, and engineering standards.

Rules:

1. Never ignore or arbitrarily modify documented requirements.
2. Never implement features outside the agreed scope without justification.
3. Respect the dependencies and priorities defined in the backlog.
4. If documentation is incomplete or contradictory, identify the issue before making significant architectural decisions.
5. Update documentation when an implementation changes an existing technical decision.

The repository's actual state must also be inspected before every task. Never assume that a feature, dependency, or file exists.

## 3. Development Workflow

Follow this workflow for every task:

### Step 1 — Inspect

- Inspect the repository structure.
- Read relevant documentation.
- Examine existing implementations.
- Identify dependencies and affected components.
- Check the current state of the backlog.

### Step 2 — Plan

Before coding:

- Understand the expected outcome.
- Identify files and modules concerned.
- Identify technical risks.
- Define acceptance criteria.
- Determine which tests are required.

For complex tasks, provide a short implementation plan first.

### Step 3 — Implement

- Work on one backlog task at a time.
- Respect task dependencies.
- Prefer small, focused changes.
- Follow the established architecture.
- Avoid unrelated modifications.
- Do not duplicate existing functionality.

### Step 4 — Validate

Before considering a task complete:

- Run relevant automated tests.
- Run linting and formatting checks.
- Run type checks where applicable.
- Verify the application builds.
- Check error handling and edge cases.
- Fix regressions introduced by the changes.

Never claim that a test passed if it was not executed.

### Step 5 — Document

- Update relevant technical documentation.
- Update the backlog task status in `docs/HAPPLY_AI_MASTER_BACKLOG.md` using the visual convention: [✅] = completed and validated (Definition of Done met), [➖] = not completed. Never switch to [✅] without executed tests, and update the progress table (Part 8.1) as well.
- Record important architectural decisions.
- Document configuration changes and environment variables.
- Mention any known limitations.

### Step 6 — Report

At the end of each task, provide:

- What was implemented.
- Files created or modified.
- Tests executed and their results.
- Remaining limitations.
- Suggested next task from the backlog.

## 4. Architecture and Code Quality

Respect the architecture defined in `docs/HAPPLY_AI_MASTER_SPEC.md`.

Mandatory standards:

- Maintain clear separation of concerns.
- Keep business logic independent of infrastructure where possible.
- Use modular and cohesive components.
- Avoid unnecessary coupling.
- Use dependency injection where appropriate.
- Keep APIs explicit and predictable.
- Centralize configuration.
- Implement consistent error handling.
- Use descriptive names.
- Prefer small functions and focused classes.
- Avoid massive files and monolithic components.

Do not introduce architectural patterns simply for the sake of using them.

Any significant architectural change must be justified and documented.

## 5. Frontend Rules

For frontend development:

- Use TypeScript with strict typing.
- Prefer reusable and accessible components.
- Keep business logic outside presentation components.
- Handle loading, empty, success, and error states.
- Validate user input.
- Avoid unnecessary dependencies.
- Ensure responsive layouts.
- Maintain consistent spacing, typography, and visual hierarchy.
- Follow the established Happly AI design system.

### Visual Identity

Happly AI must maintain a premium, modern, clean, and professional interface.

The visual direction should be inspired by Apple's design philosophy:

- Dark and elegant interface.
- Clear typography.
- Generous spacing.
- Subtle borders and surfaces.
- Smooth and restrained interactions.
- Consistent component behavior.
- Excellent readability.

Avoid:

- Excessive gradients.
- Gradients on text or buttons.
- Unnecessary animations.
- Visual clutter.
- Inconsistent components.
- Decorative elements that reduce usability.

## 6. Backend Rules

For backend development:

- Keep routes/controllers thin.
- Place business logic in dedicated services or use cases.
- Validate incoming data.
- Use typed schemas and explicit contracts.
- Implement consistent exception handling.
- Use transactions where required.
- Avoid exposing internal implementation details.
- Keep external integrations behind dedicated interfaces.
- Implement structured logging.
- Never silently swallow exceptions.

All external services must be treated as unreliable.

Implement appropriate timeouts, retries, rate limits, and failure handling where necessary.

## 7. Database Rules

- Use explicit and consistent naming conventions.
- Define appropriate primary and foreign keys.
- Add indexes based on actual query requirements.
- Use database constraints to protect data integrity.
- Create versioned migrations.
- Avoid destructive migrations without explicit justification.
- Prevent duplicate records where business rules require uniqueness.
- Never store sensitive information unnecessarily.

Database changes must be documented and tested.

## 8. AI Integration Rules

AI integrations must remain modular and provider-independent.

Rules:

- Never hardcode a single AI provider throughout the application.
- Centralize provider configuration.
- Use explicit prompts and version them where appropriate.
- Validate AI-generated structured outputs.
- Handle timeouts, errors, and invalid responses.
- Track token consumption and estimated costs.
- Implement configurable usage limits.
- Avoid unnecessary AI calls.
- Cache results when appropriate.
- Never trust AI-generated content without validation.

AI must assist the user, not make irreversible decisions on their behalf.

Never send personal information to an external AI provider without an explicit and documented data-processing decision.

## 9. Job Search and External Connectors

All job-source integrations must follow a common connector interface.

Rules:

- Keep each source independent.
- Normalize results into a shared job model.
- Implement deduplication.
- Handle pagination and rate limits.
- Respect source terms of service, robots policies, and applicable laws.
- Prefer official APIs and authorized data sources.
- Never bypass authentication, access controls, CAPTCHAs, or anti-bot protections.
- Record source attribution and retrieval timestamps.
- Handle unavailable sources gracefully.

Never create fake connectors or fabricate job listings to simulate a working integration.

Mocks are permitted only for explicitly identified tests and development environments.

## 10. Security and Privacy

Security is mandatory throughout development.

- Never commit secrets, API keys, tokens, or passwords.
- Use environment variables or an appropriate secret manager.
- Validate and sanitize external input.
- Protect authentication and authorization boundaries.
- Apply least-privilege principles.
- Prevent SQL injection, XSS, CSRF, and other common vulnerabilities.
- Avoid logging personal or sensitive information.
- Protect uploaded CVs and generated documents.
- Implement secure file handling.
- Use HTTPS for external communications.
- Keep dependencies updated and review security vulnerabilities.

Personal data must be handled according to applicable privacy regulations, including GDPR.

Never perform external actions on behalf of a user without explicit authorization.

## 11. Testing Requirements

Every meaningful feature must include appropriate tests.

Depending on the task, use:

- Unit tests.
- Integration tests.
- API tests.
- Frontend component tests.
- End-to-end tests.
- Security tests.

Prioritize tests for:

- Business rules.
- Authentication and permissions.
- Data validation.
- Job normalization and deduplication.
- AI response validation.
- CV and PDF generation.
- External connector failures.
- Cost and usage limits.

Do not remove or weaken existing tests simply to make a build pass.

## 12. Dependency Management

Before adding a dependency:

1. Check whether an existing dependency already solves the problem.
2. Evaluate maintenance and security status.
3. Consider bundle size and runtime impact.
4. Justify the addition.

Avoid unnecessary libraries, overlapping frameworks, and experimental dependencies without a clear benefit.

Never upgrade major dependencies without checking compatibility.

## 13. Error Handling and Observability

The application must be diagnosable.

- Use structured logs.
- Provide meaningful error messages.
- Avoid exposing stack traces or secrets to end users.
- Record relevant failures.
- Track external connector health.
- Monitor AI usage and costs.
- Make background jobs observable.
- Distinguish recoverable errors from fatal errors.

Never silently ignore a failure.

## 14. Git and Repository Rules

- Use clear and descriptive commit messages.
- Keep changes focused.
- Never commit generated secrets or local environment files.
- Do not overwrite unrelated user changes.
- Do not delete existing files without understanding their purpose.
- Keep the repository clean.
- Update `.gitignore` when introducing new generated or sensitive files.

Never run `git add`, `git commit`, or `git push` (see Section 17). Do not perform a release, deployment, or destructive Git operation without explicit authorization.

## 15. Forbidden Practices

The following practices are strictly prohibited:

- Claiming implementation without actual code.
- Claiming successful tests without execution.
- Creating fake integrations presented as functional.
- Hardcoding secrets or credentials.
- Ignoring documented architecture.
- Introducing unnecessary dependencies.
- Duplicating existing business logic.
- Silently changing database structures.
- Disabling tests to hide failures.
- Swallowing exceptions without logging.
- Making destructive changes without authorization.
- Deploying or spending money without explicit approval.
- Implementing unrelated features without updating the backlog.

## 16. Definition of Done

A task can be marked `DONE` only when:

- Its acceptance criteria are satisfied.
- The implementation follows the documented architecture.
- Relevant tests have been executed successfully.
- No known regression has been introduced.
- Code quality checks have passed.
- Documentation has been updated where necessary.
- The backlog status has been updated ([➖] switched to [✅] for the task, its FEATURE/EPIC rolled up only when all children are [✅]).
- Remaining limitations have been disclosed.

If any condition is not met, keep the task in the appropriate status, such as `IN_PROGRESS`, `IN_REVIEW`, `TESTING`, or `BLOCKED`.

## 17. Final Rule

- À la fin de chaque tâche, génère un message de commit **en français**, selon la convention internationale Conventional Commits (`feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`, `perf`, `build`, `style`).
  Exemple : `feat(search): ajouter le connecteur France Travail`
- Tu ne dois **jamais** exécuter `git add`, `git commit` ni `git push`, **sauf si l'utilisateur te le demande explicitement** : par défaut tu fournis uniquement le message, l'utilisateur commite lui-même.

**Never prioritize finishing a task over building it correctly.**

Every contribution must make Happly AI more reliable, maintainable, secure, and useful.

When uncertain, inspect the existing implementation, consult the documentation, explain the uncertainty, and ask for clarification rather than inventing requirements.

**These rules are mandatory for every AI agent and every development session working on Happly AI.**