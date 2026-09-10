import * as React from 'react'
import { Avatar as BaseAvatar } from '@base-ui/react/avatar'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../internal/utils'

const avatarVariants = cva(
  "relative flex size-[1em] shrink-0 items-center justify-center bg-background-strong text-center font-medium text-foreground-emphasis [&_svg:not([class*='size-'])]:size-[0.5em]",
  {
    variants: {
      size: {
        '2xs': 'text-[1.25rem]',
        xs: 'text-[1.5rem]',
        sm: 'text-[2rem]',
        md: 'text-[2.5rem]',
        lg: 'text-[3rem]',
        xl: 'text-[4rem]',
        '2xl': 'text-[5rem]',
      },
      shape: {
        rounded: 'rounded-[calc(tan(atan2(var(--radius-md),2.5rem))*100%)]',
        circle: 'rounded-full',
      },
    },
  },
)

type AvatarPresetSize = NonNullable<VariantProps<typeof avatarVariants>['size']>
type AvatarShape = NonNullable<VariantProps<typeof avatarVariants>['shape']>

interface AvatarProps extends Omit<React.ComponentProps<typeof BaseAvatar.Root>, 'size'> {
  /**
   * Full circle or rounded square.
   * @default 'circle'
   */
  shape?: AvatarShape
  /**
   * A preset scale, or a pixel number for an exact size.
   * @default 'md'
   */
  size?: AvatarPresetSize | number
}

function Avatar({ className, style, size = 'md', shape = 'circle', ...props }: AvatarProps) {
  const isNumeric = typeof size === 'number'

  const variantClass = avatarVariants({
    shape,
    size: isNumeric ? undefined : size,
  })

  const numericStyle = isNumeric ? { fontSize: `${size}px` } : undefined

  return (
    <BaseAvatar.Root
      data-slot="avatar"
      className={cn(variantClass, className)}
      style={{ ...numericStyle, ...style }}
      {...props}
    />
  )
}

type AvatarImageProps = React.ComponentProps<typeof BaseAvatar.Image>

function AvatarImage({ className, render, src, alt, ...props }: AvatarImageProps) {
  const lifted = React.isValidElement<{ src?: string; alt?: string }>(render) && render.props ? render.props : undefined

  return (
    <BaseAvatar.Image
      data-slot="avatar-image"
      className={cn('size-full rounded-[inherit] object-cover', className)}
      src={src ?? lifted?.src}
      alt={alt ?? lifted?.alt}
      render={render}
      {...props}
    />
  )
}

type AvatarFallbackProps = React.ComponentProps<typeof BaseAvatar.Fallback>

function AvatarFallback({ className, ...props }: AvatarFallbackProps) {
  return (
    <BaseAvatar.Fallback
      data-slot="avatar-fallback"
      className={cn(
        'flex size-full items-center justify-center rounded-[inherit] text-[0.4em] leading-none uppercase has-[svg]:text-[1em]',
        className,
      )}
      {...props}
    />
  )
}

interface AvatarBadgeProps extends React.ComponentPropsWithoutRef<'span'> {
  /**
   * Add a pulsing ping behind the dot (skipped under reduced motion).
   * @default false
   */
  animate?: boolean
}

function AvatarBadge({ animate = false, className, ...props }: AvatarBadgeProps) {
  return (
    <span
      data-slot="avatar-badge"
      className={cn(
        'bg-background text-success-emphasis absolute inset-e-0 bottom-0 z-1 flex size-[30%] items-center justify-center rounded-full',
        className,
      )}
      {...props}
    >
      <span className="size-[66%] rounded-full bg-current" />
      {animate && (
        <span className="animate-ping-paced absolute h-full w-full rounded-full bg-current opacity-50 motion-reduce:hidden" />
      )}
    </span>
  )
}

interface AvatarGroupProps extends React.ComponentPropsWithoutRef<'div'>, Pick<AvatarProps, 'size' | 'shape'> {
  /**
   * Stack the avatars in a row or a column.
   * @default 'horizontal'
   */
  orientation?: 'horizontal' | 'vertical'
}

function AvatarGroup({ className, size, shape, orientation = 'horizontal', children, ...props }: AvatarGroupProps) {
  const horizontal = orientation === 'horizontal'

  const decorated = React.Children.map(children, (child) => {
    if (!React.isValidElement(child) || child.type !== Avatar) return child
    const childProps = child.props as AvatarProps
    return React.cloneElement(child, {
      size: childProps.size ?? size,
      shape: childProps.shape ?? shape,
    } as Partial<AvatarProps>)
  })

  return (
    <div
      data-slot="avatar-group"
      className={cn(
        'isolate flex',
        horizontal ? 'space-x-[-0.2em]' : 'flex-col space-y-[-0.2em]',
        '*:data-[slot=avatar]:ring-background *:data-[slot=avatar]:ring-[calc(1em/12)]',
        className,
      )}
      {...props}
    >
      {decorated}
    </div>
  )
}

export { Avatar, AvatarImage, AvatarFallback, AvatarBadge, AvatarGroup }
export type { AvatarProps, AvatarImageProps, AvatarFallbackProps, AvatarBadgeProps, AvatarGroupProps }
