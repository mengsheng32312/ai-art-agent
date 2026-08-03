# UI/UX Guidelines

## Target Users

- Users who want to use ComfyUI without learning node workflows.
- Users who need a simple local tool for image generation and later asset workflows.

## Core Flow

1. Configure connection.
2. Test connection.
3. Generate image.
4. Preview result.
5. Review history.

## Information Architecture

- Left navigation: Image generation, history, connection settings.
- Top header: global layout controls only.
- Main area: one primary task per page.

## States

- Normal: editable controls, clear primary action.
- Loading: every async action must show visible progress on the triggering control and the relevant status area.
- Empty: use Ant Design Vue `Empty` or clear placeholder text.
- Error: show field-level validation for form errors and message feedback for user-triggered actions.
- Success: use message feedback and update the related status area.

## Interaction Rules

- Do not show user-triggered validation messages on initial page load.
- Test/save/generate actions must show immediate feedback.
- Disabled actions must have an understandable reason nearby.
- Local ComfyUI mode requires an installation directory before testing or saving.
- Remote API mode requires an API address before testing or saving.

## Visual Rules

- Use a light, restrained tool UI.
- Use spacing around 10px for small gaps, 20px for normal gaps, and 30px for large gaps.
- Avoid decorative gradients, excessive shadows, unnecessary cards, and large rounded corners.
- Important actions use primary buttons; secondary actions use default buttons.
- Keep visual hierarchy clear: page title, section title, field label, help text.

## Components

- Use Ant Design Vue first: `Layout`, `Menu`, `Form`, `Input`, `InputNumber`, `Select`, `Segmented`, `Button`, `Alert`, `message`, `Spin`, `Progress`, `Card`, `List`, `Empty`, `Tag`.
- Do not create custom base UI components when Ant Design Vue has an equivalent.

## Accessibility

- Keep controls keyboard operable.
- Use labels for form fields.
- Icon-only buttons need `aria-label`.
- Do not rely on color alone for validation or status.

## Responsive Behavior

- Desktop: side navigation and two-column generation layout.
- Mobile: single-column content; side navigation should later become drawer-style.
