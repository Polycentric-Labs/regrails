import { Component, type ErrorInfo, type ReactNode } from "react";
import { Card, CardBody, CardHead } from "../ui/Card";
import Button from "../ui/Button";

interface Props {
  children: ReactNode;
  /** Optional custom fallback renderer. */
  fallback?: (error: Error, reset: () => void) => ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Catches render-time errors anywhere below it (the router outlet) and shows a
 * recoverable fallback card instead of a blank white page — satisfies the
 * spec's "error boundary around every route" + "always-degrade" requirements.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Keep a console breadcrumb for DAST/debugging; no PII, synthetic data only.
    console.error("RegRails route error:", error, info.componentStack);
  }

  reset = (): void => this.setState({ error: null });

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;
    if (this.props.fallback) return this.props.fallback(error, this.reset);

    return (
      <div className="errbnd">
        <Card variant="dest">
          <CardHead
            title="Something went wrong on this page"
            desc="The rest of the app still works — the engine and the static pages don't depend on this view."
          />
          <CardBody flush>
            <div className="stack-3">
              <pre className="block" style={{ maxHeight: "10rem" }}>
                <code>{error.message}</code>
              </pre>
              <div className="row gap-2">
                <Button onClick={this.reset}>Try again</Button>
                <Button variant="outline" onClick={() => window.location.assign("/")}>
                  Back to demo
                </Button>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>
    );
  }
}

export default ErrorBoundary;
