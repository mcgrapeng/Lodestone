import * as React from 'react'
import { Toolbar as BaseToolbar } from '@base-ui/react/toolbar'
import { cn } from '../../internal/utils'

interface ToolbarProps extends React.ComponentProps<typeof BaseToolbar.Root> {}

function Toolbar({ className, ...props }: ToolbarProps) {
  return (
    <BaseToolbar.Root
      data-slot="toolbar"
      className={cn(
        'bg-background flex w-fit items-center gap-1 rounded-lg border p-1',
        'max-h-full max-w-full scrollbar-none overflow-auto *:shrink-0 [&::-webkit-scrollbar]:hidden',
        'data-[orientation=vertical]:flex-col data-[orientation=vertical]:items-stretch',
        className,
      )}
      {...props}
    />
  )
}

interface ToolbarButtonProps extends React.ComponentProps<typeof BaseToolbar.Button> {}

function ToolbarButton(props: ToolbarButtonProps) {
  return <BaseToolbar.Button data-slot="toolbar-button" {...props} />
}

interface ToolbarLinkProps extends React.ComponentProps<typeof BaseToolbar.Link> {}

function ToolbarLink(props: ToolbarLinkProps) {
  return <BaseToolbar.Link data-slot="toolbar-link" {...props} />
}

interface ToolbarInputProps extends React.ComponentProps<typeof BaseToolbar.Input> {}

function ToolbarInput(props: ToolbarInputProps) {
  return <BaseToolbar.Input data-slot="toolbar-input" {...props} />
}

interface ToolbarGroupProps extends React.ComponentProps<typeof BaseToolbar.Group> {}

function ToolbarGroup({ className, ...props }: ToolbarGroupProps) {
  return (
    <BaseToolbar.Group
      data-slot="toolbar-group"
      className={cn('flex items-center gap-1 data-[orientation=vertical]:flex-col', className)}
      {...props}
    />
  )
}

interface ToolbarSeparatorProps extends React.ComponentProps<typeof BaseToolbar.Separator> {}

function ToolbarSeparator({ className, ...props }: ToolbarSeparatorProps) {
  return (
    <BaseToolbar.Separator
      data-slot="toolbar-separator"
      className={cn(
        'bg-border shrink-0',
        'data-[orientation=vertical]:mx-0.5 data-[orientation=vertical]:h-5 data-[orientation=vertical]:w-(--border-width)',
        'data-[orientation=horizontal]:my-0.5 data-[orientation=horizontal]:h-(--border-width) data-[orientation=horizontal]:w-full',
        className,
      )}
      {...props}
    />
  )
}

export { Toolbar, ToolbarButton, ToolbarLink, ToolbarInput, ToolbarGroup, ToolbarSeparator }
export type {
  ToolbarProps,
  ToolbarButtonProps,
  ToolbarLinkProps,
  ToolbarInputProps,
  ToolbarGroupProps,
  ToolbarSeparatorProps,
}
