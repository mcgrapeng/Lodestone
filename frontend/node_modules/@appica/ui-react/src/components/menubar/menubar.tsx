'use client'

import * as React from 'react'
import { Menubar as BaseMenubar } from '@base-ui/react/menubar'
import { cn } from '../../internal/utils'
import { navigationLinkVariants } from '../navigation/navigation-link-variants'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuGroupLabel,
  DropdownMenuItem,
  DropdownMenuLinkItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '../dropdown-menu/dropdown-menu'

type MenubarVariant = 'pill' | 'line'
type MenubarSize = 'sm' | 'md' | 'lg'
type MenubarOrientation = 'horizontal' | 'vertical'

interface MenubarContextValue {
  variant: MenubarVariant
  size: MenubarSize
  orientation: MenubarOrientation
}

const MenubarContext = React.createContext<MenubarContextValue | null>(null)

function useMenubarContext() {
  const ctx = React.useContext(MenubarContext)
  if (!ctx) {
    throw new Error('Menubar sub-components must be rendered inside <Menubar>')
  }
  return ctx
}

type BaseMenubarRootProps = React.ComponentProps<typeof BaseMenubar>

interface MenubarProps extends BaseMenubarRootProps {
  /**
   * Trigger appearance - hover/active pill, or an animated underline.
   * @default 'pill'
   */
  variant?: MenubarVariant
  /**
   * Scales the triggers, popups, and items together.
   * @default 'md'
   */
  size?: MenubarSize
}

const HORIZONTAL_GAP: Partial<Record<MenubarVariant, string>> = {
  pill: 'gap-0.5',
  line: 'gap-7',
}

const VERTICAL_GAP: Partial<Record<MenubarVariant, string>> = {
  pill: 'gap-0.5',
}

function Menubar({
  className,
  variant = 'pill',
  size = 'md',
  orientation = 'horizontal',
  children,
  ...rest
}: MenubarProps) {
  const ctx = React.useMemo<MenubarContextValue>(() => ({ variant, size, orientation }), [variant, size, orientation])
  const gap = (orientation === 'vertical' ? VERTICAL_GAP : HORIZONTAL_GAP)[variant]
  return (
    <MenubarContext.Provider value={ctx}>
      <BaseMenubar
        data-slot="menubar"
        orientation={orientation}
        className={cn(
          'flex w-fit',
          orientation === 'vertical' ? 'flex-col items-stretch' : 'items-center',
          gap,
          className,
        )}
        {...rest}
      >
        {children}
      </BaseMenubar>
    </MenubarContext.Provider>
  )
}

type DropdownMenuRootProps = React.ComponentProps<typeof DropdownMenu>

interface MenubarMenuProps extends Omit<DropdownMenuRootProps, 'size'> {}

function MenubarMenu(props: MenubarMenuProps) {
  const { size } = useMenubarContext()
  return <DropdownMenu size={size} {...props} />
}

type MenubarTriggerProps = React.ComponentProps<typeof DropdownMenuTrigger>

function MenubarTrigger({ className, ...props }: MenubarTriggerProps) {
  const { variant, size, orientation } = useMenubarContext()
  return (
    <DropdownMenuTrigger
      data-slot="menubar-trigger"
      data-orientation={orientation}
      className={cn(navigationLinkVariants({ variant, size }), 'outline-hidden', className)}
      {...props}
    />
  )
}

type MenubarContentProps = React.ComponentProps<typeof DropdownMenuContent>

function MenubarContent({ side, align, ...props }: MenubarContentProps) {
  const ctx = useMenubarContext()
  const vertical = ctx.orientation === 'vertical'
  return (
    <DropdownMenuContent
      data-slot="menubar-content"
      side={side ?? (vertical ? 'inline-end' : undefined)}
      align={align ?? (vertical ? 'start' : undefined)}
      {...props}
    />
  )
}

type MenubarItemProps = React.ComponentProps<typeof DropdownMenuItem>

function MenubarItem(props: MenubarItemProps) {
  return <DropdownMenuItem data-slot="menubar-item" {...props} />
}

type MenubarLinkItemProps = React.ComponentProps<typeof DropdownMenuLinkItem>

function MenubarLinkItem(props: MenubarLinkItemProps) {
  return <DropdownMenuLinkItem data-slot="menubar-link-item" {...props} />
}

type MenubarGroupProps = React.ComponentProps<typeof DropdownMenuGroup>

function MenubarGroup(props: MenubarGroupProps) {
  return <DropdownMenuGroup data-slot="menubar-group" {...props} />
}

type MenubarGroupLabelProps = React.ComponentProps<typeof DropdownMenuGroupLabel>

function MenubarGroupLabel(props: MenubarGroupLabelProps) {
  return <DropdownMenuGroupLabel data-slot="menubar-group-label" {...props} />
}

type MenubarRadioGroupProps = React.ComponentProps<typeof DropdownMenuRadioGroup>

function MenubarRadioGroup(props: MenubarRadioGroupProps) {
  return <DropdownMenuRadioGroup data-slot="menubar-radio-group" {...props} />
}

type MenubarRadioItemProps = React.ComponentProps<typeof DropdownMenuRadioItem>

function MenubarRadioItem(props: MenubarRadioItemProps) {
  return <DropdownMenuRadioItem data-slot="menubar-radio-item" {...props} />
}

type MenubarCheckboxItemProps = React.ComponentProps<typeof DropdownMenuCheckboxItem>

function MenubarCheckboxItem(props: MenubarCheckboxItemProps) {
  return <DropdownMenuCheckboxItem data-slot="menubar-checkbox-item" {...props} />
}

type MenubarSeparatorProps = React.ComponentProps<typeof DropdownMenuSeparator>

function MenubarSeparator(props: MenubarSeparatorProps) {
  return <DropdownMenuSeparator data-slot="menubar-separator" {...props} />
}

type MenubarSubProps = React.ComponentProps<typeof DropdownMenuSub>

function MenubarSub(props: MenubarSubProps) {
  return <DropdownMenuSub {...props} />
}

type MenubarSubTriggerProps = React.ComponentProps<typeof DropdownMenuSubTrigger>

function MenubarSubTrigger(props: MenubarSubTriggerProps) {
  return <DropdownMenuSubTrigger data-slot="menubar-sub-trigger" {...props} />
}

type MenubarSubContentProps = React.ComponentProps<typeof DropdownMenuSubContent>

function MenubarSubContent(props: MenubarSubContentProps) {
  return <DropdownMenuSubContent data-slot="menubar-sub-content" {...props} />
}

export {
  Menubar,
  MenubarMenu,
  MenubarTrigger,
  MenubarContent,
  MenubarItem,
  MenubarLinkItem,
  MenubarGroup,
  MenubarGroupLabel,
  MenubarRadioGroup,
  MenubarRadioItem,
  MenubarCheckboxItem,
  MenubarSeparator,
  MenubarSub,
  MenubarSubTrigger,
  MenubarSubContent,
}
export type {
  MenubarProps,
  MenubarMenuProps,
  MenubarTriggerProps,
  MenubarContentProps,
  MenubarItemProps,
  MenubarLinkItemProps,
  MenubarGroupProps,
  MenubarGroupLabelProps,
  MenubarRadioGroupProps,
  MenubarRadioItemProps,
  MenubarCheckboxItemProps,
  MenubarSeparatorProps,
  MenubarSubProps,
  MenubarSubTriggerProps,
  MenubarSubContentProps,
}
