# Reusable LaTeX Template Items

Some project templates ship with custom LaTeX items (environments, commands, color tokens) that make fragments look sharper than plain `\begin{quote}` / `\textbf{}` / `lstlisting`. This file catalogs items the skill can recognize AND documents how a user can map Markdown patterns onto them.

**Important**: the skill does NOT auto-load any template. If a project uses `gist-preprint.sty` (DS-Lab preprint template) the user must keep that `\usepackage{gist-preprint}` in main.tex themselves; the skill only provides the **preprocess mappings** that emit the matching environments.

## How to opt in

Set `template_preset: "gist-preprint"` in the Phase 6 plan `manifest.yaml` (or pass `--template-preset gist-preprint` to `md_inject.sh`). When enabled, the preprocess pipeline swaps these pandoc-default LaTeX constructs for the richer custom ones:

| Markdown input | Default pandoc LaTeX | With `gist-preprint` preset |
|---|---|---|
| `> **Note**: X` blockquote | `\begin{quote}\textbf{Note}: X\end{quote}` | `\begin{highlightbox}\textbf{Note}: X\end{highlightbox}` |
| `> [!research] X` Obsidian callout | `\begin{quote}X\end{quote}` | `\begin{researchquestion}X\end{researchquestion}` |
| ` ```algorithm ` fenced block | `\begin{lstlisting}...\end{lstlisting}` | `\begin{algorithm}\begin{algorithmic}[1]...\end{algorithmic}\end{algorithm}` |
| `56.3 ± 1.2` inline | `56.3 ± 1.2` | `\val{56.3}{1.2}` |
| `[red:important]` inline | `important` | `\tokenred{important}` |

When the preset is not active (the default), the skill falls back to stock LaTeX constructs — `\begin{quote}`, `lstlisting`, etc. — and Round 4.5's `unwrap_blockquotes` / `strip_prose_bold` rules apply.

## Available items — gist-preprint.sty

The file `pre-print-template(ds-lab)/gist-preprint.sty` defines:

| Name | Kind | Signature | When useful |
|---|---|---|---|
| `researchquestion` | environment | `\begin{researchquestion}...\end{researchquestion}` | Framed red-border italic centered box. One-paragraph research question hooks. |
| `highlightbox` | environment | `\begin{highlightbox}...\end{highlightbox}` | Blue left-border soft callout. "Note", "Warning", key insight callouts. |
| `abstractbox` | environment | `\begin{abstract}...\end{abstract}` (auto-loaded by document class) | Abstract with logo bar. |
| `\token{color}{text}` | macro | `\token{gistblue}{SFT}` | Color-coded inline tag (like "SFT / DPO / GRPO" badges). |
| `\tokenred{x}`, `\tokenblue{x}`, `\tokengold{x}`, `\tokengray{x}` | macro | `\tokenred{NEW}` | Convenience wrappers for `\token{}`. |
| `\val{mean}{stderr}` | macro | `\val{56.3}{1.2}` | Table cell with mean + small gray `± stderr` subscript. |
| `algorithm` / `algorithmic` | environment | `\begin{algorithm}[t]\caption{X}\label{alg:y}\begin{algorithmic}[1]\Require...\State...\end{algorithmic}\end{algorithm}` | Numbered pseudocode blocks (loaded via `\RequirePackage{algorithm, algpseudocode}`). |

## Preprocess mapping — gist-preprint preset

The following mappings are applied ONLY when `template_preset=gist-preprint` (not the default). They intentionally leave non-matching input untouched.

### Blockquote → `highlightbox` / `researchquestion`

Obsidian-style callout syntax:

```
> [!note] Key finding
> The distribution is bimodal because ...
```

```
> [!research]
> Can FSPM be separated from instrumental helpfulness?
```

The `[!note]` / `[!warn]` / `[!tip]` / `[!info]` variants map to `highlightbox`; `[!research]` / `[!question]` map to `researchquestion`.

Plain `> ...` (no `[!kind]` token) still falls through to `\begin{quote}` which Round 4.5 strips by default.

### Algorithm fence

Fenced block with `algorithm` as info-string:

<pre>
```algorithm
caption: Monte Carlo tree search
label: alg:mcts
Require: root node $v_0$, budget $T$
Ensure: action $a^\star$
For $t = 1, \ldots, T$
  Select leaf $v$ via UCT
  Expand $v$, simulate, backprop
End For
Return best child of $v_0$
```
</pre>

Emits:

```latex
\begin{algorithm}[t]
  \caption{Monte Carlo tree search}
  \label{alg:mcts}
  \begin{algorithmic}[1]
    \Require root node $v_0$, budget $T$
    \Ensure action $a^\star$
    \For{$t = 1, \ldots, T$}
      \State Select leaf $v$ via UCT
      \State Expand $v$, simulate, backprop
    \EndFor
    \State \Return best child of $v_0$
  \end{algorithmic}
\end{algorithm}
```

The parser recognizes: `Require:`, `Ensure:`, `For ... End For`, `If ... Else ... End If`, `While ... End While`, `Return`, plain lines → `\State`. Lines starting with `caption:` / `label:` become `\caption{}` / `\label{}`.

### `\val{}` — mean ± stderr

Inline pattern `NUMBER ± NUMBER` (either ASCII `+-` or Unicode `±`) inside a table cell becomes `\val{NUMBER}{NUMBER}`. Example:

| Method | Accuracy |
|---|---:|
| SFT    | 42.1 ± 1.8 |
| + DPO  | 48.3 ± 1.5 |

becomes

```latex
\val{42.1}{1.8}
\val{48.3}{1.5}
```

Only triggered inside `\begin{tabular}...\end{tabular}` to avoid rewriting stat prose.

### `\tokenred{}` / `\tokenblue{}` / `\tokengold{}` / `\tokengray{}` — color-coded inline tags

Markdown inline code with a known color prefix: `` `red:URGENT` `` → `\tokenred{URGENT}`. Supported prefixes: `red:`, `blue:`, `gold:`, `gray:`.

## Without the preset — Round 4.5 defaults

If `template_preset` is omitted (or explicitly set to `none`), the skill preserves the behavior documented elsewhere:

- `>` blockquotes → **stripped** (`unwrap_blockquotes=True`); content stays as plain paragraph.
- Prose-emphasis `\textbf{...}` (>12 chars OR sentence punctuation) → stripped.
- Fenced code blocks with pipe-heavy content → ASCII-art placeholder (content preserved as `\fbox{...}`).
- `lstlisting` emission → accompanied by a defensive `\lstset{basicstyle=\footnotesize\ttfamily, breaklines=true}` preamble snippet.
- Trailing italic caption lines after floats → `\caption{}` inside the float.

## Extending with another template

To teach the skill about a new template (e.g. `my-lab-style.sty`):

1. Enumerate the template's custom items (envs + macros) in a new `references/template-items-<name>.md`.
2. Write a mapping function in `scripts/md_inject/preprocess/template_presets.py` (create if it does not exist) keyed on the preset name.
3. Wire the preset name into `md_inject_convert.py:_convert_one` by passing `template_preset` through to `PostprocessConfig`.
4. Add a smoke test MD in `examples/md_inject/sample-<name>.md` + expected fragment `sample-<name>.tex`.

This pattern keeps preset-specific logic out of the default path, so projects without the template see no behavior change.
