import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
  stack: string | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, stack: null }

  static getDerivedStateFromError(error: Error): State {
    return { error, stack: error.stack ?? null }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // ponytail: surface the failing component tree next to the error so the
    // blank-page case becomes a readable card instead of a silently unmounted root.
    console.error('[ErrorBoundary]', error, info)
  }

  reset = () => {
    this.setState({ error: null, stack: null })
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="mx-auto mt-12 max-w-3xl px-6">
          <div className="card-surface border-red-500/30 p-6">
            <div className="mb-3 flex items-center gap-2 text-error">
              <AlertTriangle className="h-5 w-5" />
              <h2 className="text-base font-semibold">运行时错误</h2>
              <button
                type="button"
                onClick={this.reset}
                className="ml-auto inline-flex items-center gap-1 rounded-md bg-background-muted px-2 py-1 text-xs text-foreground-muted hover:bg-background-strong"
              >
                <RefreshCw className="h-3 w-3" /> 重试
              </button>
            </div>
            <p className="mb-2 text-sm text-foreground-muted">{this.state.error.message}</p>
            {this.state.stack && (
              <pre className="max-h-64 overflow-auto rounded bg-background-inverse/40 p-3 text-[11px] text-foreground-subtle">
                {this.state.stack}
              </pre>
            )}
            <p className="mt-3 text-[11px] text-foreground-subtle">
              完整错误堆栈见浏览器 DevTools Console。
            </p>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
