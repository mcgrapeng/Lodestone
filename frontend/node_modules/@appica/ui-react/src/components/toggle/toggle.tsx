import { Toggle as BaseToggle } from '@base-ui/react/toggle'

interface ToggleProps extends BaseToggle.Props {}

function Toggle(props: ToggleProps) {
  return <BaseToggle data-slot="toggle" {...props} />
}

export { Toggle }
export type { ToggleProps }
