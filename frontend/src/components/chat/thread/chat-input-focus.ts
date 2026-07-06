interface LoadingChangeInput {
  wasLoading: boolean;
  isLoading: boolean;
}

export function shouldFocusAfterLoadingChange({
  wasLoading,
  isLoading,
}: LoadingChangeInput): boolean {
  return wasLoading && !isLoading;
}
