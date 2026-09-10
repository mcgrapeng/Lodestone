'use client'

import * as React from 'react'
import { type VariantProps } from 'class-variance-authority'
import { cn } from '../../internal/utils'
import { describeColor, normalizeColor } from '../../internal/color-control'
import {
  ColorPickerContext,
  type ColorPickerContextValue,
  useRequiredColorPickerContext,
} from '../../internal/color-picker-context'
import { ColorArea } from '../color-area/color-area'
import { ColorSlider } from '../color-slider/color-slider'
import { ColorSwatch, type ColorSwatchProps } from '../color-swatch/color-swatch'
import { buttonVariants } from '../button/button-variants'
import { Input, type InputProps } from '../input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
  type PopoverContentProps,
  type PopoverProps,
} from '../popover/popover'
import { type Color, type ColorFormat, formatColor, safeParseColor, withChannelValue } from '../../lib/color'

const DEFAULT_VALUE = '#ffffff'

type ColorPickerSize = 'sm' | 'md' | 'lg'
type ColorPickerVariant = 'ghost' | 'outline' | 'soft' | 'flush'
type ColorPickerSwatchPosition = 'start' | 'end'
type ColorPickerSwatchShape = NonNullable<ColorSwatchProps['shape']>

const TRIGGER_SIZES: Record<ColorPickerSize, { button: ColorPickerSize; swatch: number; iconSwatch: number }> = {
  // A swatch-only trigger is square, so its swatch takes the next size up.
  sm: { button: 'sm', swatch: 20, iconSwatch: 24 },
  md: { button: 'md', swatch: 24, iconSwatch: 28 },
  lg: { button: 'lg', swatch: 28, iconSwatch: 32 },
}

const ICON_BUTTON_SIZES: Record<ColorPickerSize, 'icon-sm' | 'icon-md' | 'icon-lg'> = {
  sm: 'icon-sm',
  md: 'icon-md',
  lg: 'icon-lg',
}

/**
 * `flush` is `ghost` with the button shell taken off: no box, no padding, no corner and
 * no hover fill, so the swatch lines up with whatever sits above or below it.
 */
const FLUSH_CLASSES =
  'size-auto rounded-none p-0 hover:before:bg-transparent data-popup-open:before:bg-transparent data-pressed:before:bg-transparent'

/**
 * Pulls the swatch back out of the button's `px-*` so the gap beside it matches the one
 * the button's height leaves above and below it: half the difference between the two,
 * at every size. A swatch-only trigger is already square, so it needs none of this.
 */
const SWATCH_OFFSETS: Record<ColorPickerSize, Record<ColorPickerSwatchPosition, string>> = {
  sm: { start: '-ms-2.5', end: '-me-2.5' },
  md: { start: '-ms-3', end: '-me-3' },
  lg: { start: '-ms-3.5', end: '-me-3.5' },
}

const FORMAT_LABELS: Record<ColorFormat, string> = {
  hex: 'Hex',
  hexa: 'Hex',
  rgb: 'RGB',
  rgba: 'RGB',
  hsl: 'HSL',
  hsla: 'HSL',
  hsb: 'HSB',
  hsba: 'HSB',
  oklch: 'OKLCH',
  oklcha: 'OKLCH',
}

const OPAQUE_FORMATS: Partial<Record<ColorFormat, ColorFormat>> = {
  hexa: 'hex',
  rgba: 'rgb',
  hsla: 'hsl',
  hsba: 'hsb',
  oklcha: 'oklch',
}

/**
 * An alpha-carrying format drops back to its opaque twin at full opacity, so a solid
 * color is written `#a855f7` rather than `#a855f7ff` and only grows the alpha when
 * there is one to show.
 */
function displayFormat(format: ColorFormat, color: Color): ColorFormat {
  return color.alpha < 1 ? format : (OPAQUE_FORMATS[format] ?? format)
}

const panelClasses = 'flex w-fit min-w-50 flex-col gap-3'

interface ColorPickerProps extends Omit<
  React.HTMLAttributes<HTMLElement>,
  'color' | 'defaultValue' | 'onChange' | 'children'
> {
  /** Selected color. Pass a `Color` or any CSS color string to control the component. */
  value?: Color | string
  /**
   * Color selected before any interaction, when the component is uncontrolled.
   * @default '#ffffff'
   */
  defaultValue?: Color | string
  /** Fires on every change, including each frame of a drag inside the panel. */
  onValueChange?: (value: Color) => void
  /** Fires once a gesture ends, with the color that was landed on. */
  onValueCommitted?: (value: Color) => void
  /**
   * Panel contents. Any `ColorArea`, `ColorSlider`, `ColorSwatch` or `ColorSwatchPicker`
   * in here reads and writes the picker's color, so no value wiring is needed. Leave it
   * off for the default panel: an HSB area, a hue slider and a text input, plus a preview
   * swatch when `inline` leaves no trigger to show one.
   */
  children?: React.ReactNode
  /**
   * Format the trigger and the text input write the color in. Defaults to `'hexa'` when
   * `alpha` is set. An alpha format collapses to its opaque twin whenever the color is
   * fully opaque, so a solid color never picks up a trailing `ff`.
   * @default 'hex'
   */
  format?: ColorFormat
  /**
   * Add an alpha slider to the default panel, and back the preview with a checkerboard.
   * @default false
   */
  alpha?: boolean
  /**
   * Add a screen color-sampling button to the default panel. It renders only where the
   * browser supports the EyeDropper API, so there is no dead control on Firefox or Safari.
   * @default false
   */
  eyedropper?: boolean
  /**
   * Render the panel in place instead of behind a trigger and a popover. The trigger
   * props (`label`, `trigger`, `size`, the popover ones) do nothing in this mode.
   * @default false
   */
  inline?: boolean
  /**
   * Prevent interaction and dim the trigger and every control in the panel.
   * @default false
   */
  disabled?: boolean
  /**
   * Height and text scale of the default trigger.
   * @default 'md'
   */
  size?: ColorPickerSize
  /**
   * Visual style of the default trigger, from `Button`'s set. `flush` takes the button
   * shell off entirely, leaving the swatch and the label on their own.
   * @default 'ghost'
   */
  variant?: ColorPickerVariant
  /**
   * Text beside the swatch in the default trigger. Defaults to the color, formatted with
   * `format`. Pass `null` for a swatch-only square button, and pair a non-string node
   * with `aria-label`.
   */
  label?: React.ReactNode
  /**
   * Rounded square or full circle, for the swatch on the default trigger.
   * @default 'rounded'
   */
  swatchShape?: ColorPickerSwatchShape
  /**
   * Which side of the label the default trigger's swatch sits on. It is inset from that
   * edge by the same gap the button's height leaves above and below it.
   * @default 'start'
   */
  swatchPosition?: ColorPickerSwatchPosition
  /**
   * Element to open the panel from, in place of the default swatch button. `null` renders
   * no trigger at all, for a panel driven by `open` and pointed at something you own with
   * `popoverProps.anchor`. `className` and the forwarded attributes land on the trigger,
   * so they have nowhere to go in that mode.
   */
  trigger?: React.ReactElement | null
  /** Controlled open state of the popover. Pair with `onOpenChange`. */
  open?: boolean
  /**
   * Uncontrolled initial open state of the popover.
   * @default false
   */
  defaultOpen?: boolean
  /**
   * Fires when the popover opens or closes. The second argument carries the `reason` and
   * a `cancel()` that stops Base UI acting on the event.
   */
  onOpenChange?: PopoverProps['onOpenChange']
  /**
   * Preferred popover side.
   * @default 'bottom'
   */
  side?: PopoverContentProps['side']
  /**
   * Popover alignment.
   * @default 'start'
   */
  align?: PopoverContentProps['align']
  /**
   * Gap between the trigger and the popover.
   * @default 6
   */
  sideOffset?: number
  /** Escape hatch forwarded to the inner `PopoverContent` (collision props, `className`, …). */
  popoverProps?: Partial<PopoverContentProps>
  /** Name of the hidden input, used when submitting an HTML form. */
  name?: string
  /** `id` of the `<form>` the hidden input belongs to, when it sits outside it. */
  form?: string
}

function ColorPicker({
  value,
  defaultValue = DEFAULT_VALUE,
  onValueChange,
  onValueCommitted,
  children,
  format: formatProp,
  alpha = false,
  eyedropper = false,
  inline = false,
  disabled = false,
  size = 'md',
  variant = 'ghost',
  label,
  swatchShape = 'rounded',
  swatchPosition = 'start',
  trigger,
  open,
  defaultOpen = false,
  onOpenChange,
  side = 'bottom',
  align = 'start',
  sideOffset = 6,
  popoverProps,
  name,
  form,
  className,
  'aria-label': ariaLabel,
  ...props
}: ColorPickerProps) {
  const [uncontrolled, setUncontrolled] = React.useState<Color>(() => normalizeColor(defaultValue))
  const [internalOpen, setInternalOpen] = React.useState(defaultOpen)

  const controlled = value !== undefined
  const color = controlled ? normalizeColor(value) : uncontrolled
  const format = formatProp ?? (alpha ? 'hexa' : 'hex')

  // Kept in a ref so the context object only changes with the color, not with a caller
  // that re-creates its handlers on every render.
  const latestRef = React.useRef({ controlled, onValueChange, onValueCommitted })
  latestRef.current = { controlled, onValueChange, onValueCommitted }

  const context = React.useMemo<ColorPickerContextValue>(
    () => ({
      value: color,
      format,
      disabled,
      setValue: (next) => {
        if (!latestRef.current.controlled) setUncontrolled(next)
        latestRef.current.onValueChange?.(next)
      },
      commitValue: (next) => latestRef.current.onValueCommitted?.(next),
    }),
    [color, format, disabled],
  )

  const panel = children ?? (
    <>
      <ColorArea colorSpace="hsb" xChannel="saturation" yChannel="brightness" aria-label="Saturation and brightness" />
      <div className="flex items-center gap-3">
        {eyedropper && <ColorPickerEyeDropper />}
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <ColorSlider channel="hue" />
          {alpha && <ColorSlider channel="alpha" />}
        </div>
        {/* The trigger already previews the color; only an inline panel has to. */}
        {inline && <ColorSwatch size="sm" shape="circle" className="shrink-0" />}
      </div>
      <ColorPickerInput />
    </>
  )

  const valueText = formatColor(color, displayFormat(format, color))
  const hiddenInput = name ? <input type="hidden" name={name} form={form} value={valueText} /> : null

  if (inline) {
    return (
      <ColorPickerContext.Provider value={context}>
        <div
          role="group"
          aria-label={ariaLabel}
          {...props}
          data-slot="color-picker"
          {...(disabled ? { 'data-disabled': '' } : {})}
          className={cn(panelClasses, className)}
        >
          {panel}
          {hiddenInput}
        </div>
      </ColorPickerContext.Provider>
    )
  }

  const description = describeColor(color)
  const iconOnly = label === null
  const sizes = TRIGGER_SIZES[size]
  const swatch = (
    <ColorSwatch
      aria-hidden="true"
      size={iconOnly ? sizes.iconSwatch : sizes.swatch}
      shape={swatchShape}
      className={iconOnly || variant === 'flush' ? undefined : SWATCH_OFFSETS[size][swatchPosition]}
    />
  )

  const defaultTrigger = (
    <button type="button">
      {swatchPosition === 'start' && swatch}
      {!iconOnly && <span>{label ?? valueText}</span>}
      {swatchPosition === 'end' && swatch}
      {!ariaLabel && <span className="sr-only">{description}</span>}
    </button>
  )

  return (
    <ColorPickerContext.Provider value={context}>
      <Popover
        open={open ?? internalOpen}
        onOpenChange={(next, details) => {
          onOpenChange?.(next, details)
          if (open === undefined && !details.isCanceled) setInternalOpen(next)
        }}
      >
        {trigger !== null && (
          <PopoverTrigger
            aria-label={ariaLabel && `${ariaLabel}, ${description}`}
            {...props}
            data-slot="color-picker-trigger"
            disabled={disabled}
            // The variant classes ride on the wrapper so `cn` resolves them against a
            // consumer `className`; the rendered element carries none of its own.
            className={cn(
              !trigger && [
                buttonVariants({
                  variant: variant === 'flush' ? 'ghost' : variant,
                  size: iconOnly ? ICON_BUTTON_SIZES[size] : sizes.button,
                }),
                variant === 'flush' && FLUSH_CLASSES,
              ],
              className,
            )}
            render={trigger ?? defaultTrigger}
          />
        )}
        <PopoverContent
          side={side}
          align={align}
          sideOffset={sideOffset}
          arrow={false}
          // The popup is a dialog, and a dialog with no title still needs a name.
          aria-label={ariaLabel ?? 'Color picker'}
          {...popoverProps}
          data-slot="color-picker-panel"
          className={cn(panelClasses, 'max-w-none p-3', popoverProps?.className)}
        >
          {panel}
        </PopoverContent>
      </Popover>
      {hiddenInput}
    </ColorPickerContext.Provider>
  )
}

interface ColorPickerInputProps extends Omit<
  InputProps,
  'value' | 'defaultValue' | 'onChange' | 'color' | 'clearable' | 'onClear'
> {
  /** Format the color is written in. Defaults to the enclosing picker's `format`. */
  format?: ColorFormat
}

/**
 * Reads any CSS color string the library can parse, not just the format it prints, so
 * pasting `rgb(…)` into a hex field works. A bare `ff0080` is accepted as hex too.
 */
function parseInputColor(text: string): Color | undefined {
  const trimmed = text.trim()
  return safeParseColor(/^[0-9a-f]{3,8}$/i.test(trimmed) ? `#${trimmed}` : trimmed)
}

function ColorPickerInput({ format: formatProp, className, ...props }: ColorPickerInputProps) {
  const picker = useRequiredColorPickerContext('ColorPickerInput')
  const format = formatProp ?? picker.format
  const [draft, setDraft] = React.useState<string | null>(null)

  const commit = () => {
    const parsed = draft === null ? undefined : parseInputColor(draft)
    if (parsed) picker.commitValue(parsed)
    setDraft(null)
  }

  return (
    <Input
      inputSize="sm"
      spellCheck={false}
      autoComplete="off"
      autoCorrect="off"
      autoCapitalize="off"
      aria-label={FORMAT_LABELS[format]}
      {...props}
      data-slot="color-picker-input"
      // An <input> is intrinsically 20 characters wide, and `w-full` cannot resolve
      // during intrinsic sizing - so in the panel's `w-fit` column those 20 characters,
      // not the color area, would decide how wide the panel is. Worse on a coarse
      // pointer, where the field steps up to 16px type.
      inputProps={{ size: 1, ...props.inputProps }}
      disabled={props.disabled ?? picker.disabled}
      value={draft ?? formatColor(picker.value, displayFormat(format, picker.value))}
      className={cn('font-mono', className)}
      onChange={(event) => {
        const next = event.target.value
        setDraft(next)
        const parsed = parseInputColor(next)
        if (parsed) picker.setValue(parsed)
      }}
      onBlur={(event) => {
        props.onBlur?.(event)
        commit()
      }}
      onKeyDown={(event) => {
        props.onKeyDown?.(event)
        if (event.defaultPrevented) return
        if (event.key === 'Enter') {
          event.preventDefault()
          commit()
        } else if (event.key === 'Escape') {
          setDraft(null)
        }
      }}
    />
  )
}

interface EyeDropperApi {
  new (): { open: (options?: { signal?: AbortSignal }) => Promise<{ sRGBHex: string }> }
}

interface ColorPickerEyeDropperProps extends Omit<React.ComponentPropsWithoutRef<'button'>, 'color' | 'children'> {
  /**
   * Visual style, from the same set `Button` offers.
   * @default 'ghost'
   */
  variant?: VariantProps<typeof buttonVariants>['variant']
  /**
   * Height and padding, from the same set `Button` offers.
   * @default 'icon-sm'
   */
  size?: VariantProps<typeof buttonVariants>['size']
  /** Icon rendered inside the button. */
  children?: React.ReactNode
}

function ColorPickerEyeDropper({
  variant = 'ghost',
  size = 'icon-sm',
  className,
  disabled,
  children = <PipetteIcon />,
  'aria-label': ariaLabel = 'Pick a color from the screen',
  ...props
}: ColorPickerEyeDropperProps) {
  const picker = useRequiredColorPickerContext('ColorPickerEyeDropper')
  // Resolved after mount rather than during render: the server has no `window`, and a
  // guess either way would mismatch the client on hydration.
  const [supported, setSupported] = React.useState(false)
  React.useEffect(() => setSupported('EyeDropper' in window), [])

  if (!supported) return null

  const off = disabled ?? picker.disabled

  const sample = async () => {
    const EyeDropper = (window as unknown as { EyeDropper: EyeDropperApi }).EyeDropper
    let result: { sRGBHex: string }
    try {
      result = await new EyeDropper().open()
    } catch {
      return
    }
    const sampled = safeParseColor(result.sRGBHex)
    if (!sampled) return
    // The API only reports opaque colors, so carry the picker's own alpha across.
    const next = withChannelValue(sampled, 'alpha', picker.value.alpha)
    picker.setValue(next)
    picker.commitValue(next)
  }

  return (
    <button
      type="button"
      aria-label={ariaLabel}
      {...props}
      data-slot="color-picker-eyedropper"
      disabled={off}
      {...(off ? { 'data-disabled': '' } : {})}
      className={cn(
        buttonVariants({ variant, size }),
        'text-foreground-muted hover:text-foreground shrink-0',
        className,
      )}
      onClick={(event) => {
        props.onClick?.(event)
        if (!event.defaultPrevented) void sample()
      }}
    >
      {children}
    </button>
  )
}

function PipetteIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="m2 22 1-1h3l9-9" />
      <path d="M3 21v-3l9-9" />
      <path d="m15 6 3.4-3.4a2.1 2.1 0 1 1 3 3L18 9l.4.4a1 1 0 1 1-3 3l-3.8-3.8a1 1 0 1 1 3-3l.4.4Z" />
    </svg>
  )
}

export { ColorPicker, ColorPickerInput, ColorPickerEyeDropper }
export type { ColorPickerProps, ColorPickerInputProps, ColorPickerEyeDropperProps }
