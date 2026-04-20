/**
 * Public layout — no auth, no sidebar.
 * Used for login, onboarding, and other unauthenticated pages.
 */
export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

