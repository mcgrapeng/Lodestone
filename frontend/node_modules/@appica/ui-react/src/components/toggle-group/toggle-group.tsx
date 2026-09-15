import { ToggleGroup as BaseToggleGroup } from '@base-ui/react/toggle-group'
import { cn } from '../../internal/utils'

interface ToggleGroupProps extends BaseToggleGroup.Props {}

function ToggleGroup({ className, ...props }: ToggleGroupProps) {
  return (
    <BaseToggleGroup
      data-slot="toggle-group"
      className={cn(
        'flex w-fit items-center gap-1',
        'data-[orientation=vertical]:flex-col data-[orientation=vertical]:items-stretch',
        className,
      )}
      {...props}
    />
  )
}

export { ToggleGroup }
export type { ToggleGroupProps }
