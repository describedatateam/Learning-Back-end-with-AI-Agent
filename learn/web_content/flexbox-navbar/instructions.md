# Lay out a navigation bar with Flexbox

Almost every site has a bar at the top: a logo on one side, links on the other. **Flexbox** is the CSS tool for this kind of one-row layout.

## How Flexbox works

Put `display: flex` on a **parent**, and its direct children line up in a row. Then the parent decides where they go:

| Property | What it does |
| --- | --- |
| `justify-content` | spreads items **along** the row: `flex-start`, `center`, `space-between` |
| `align-items` | lines items up **across** the row: `flex-start`, `center`, `stretch` |
| `flex-wrap` | `wrap` lets items move to the next line when there is no room |
| `gap` | the space between items |

```css
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
```

## Your task

The page has a `.site-nav` bar holding a `.logo` link and a `.links` list. Right now everything is stacked. In `style.css`:

1. Make `.site-nav` a flex container.
2. Push the logo and the links to opposite ends.
3. Centre them vertically.
4. Let the links wrap to a new line on narrow screens.
5. Remove the bullets from `.links`.
6. Put the links in a row with `16px` between them.

Watch the **Preview** as you type, then press **Run tests**.
