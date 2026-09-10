import * as React from 'react'
import { Form as BaseForm } from '@base-ui/react/form'

type FormProps = React.ComponentProps<typeof BaseForm>

function Form(props: FormProps) {
  return <BaseForm data-slot="form" {...props} />
}

export { Form }
export type { FormProps }
