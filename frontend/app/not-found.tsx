import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6 text-center">
      <div className="crm-card max-w-md w-full p-8">
        <h1 className="text-2xl font-medium text-[#171717] tabular-nums mb-2">Page not found</h1>
        <p className="text-sm text-slate-600 mb-6">
          The workspace route or resource you requested could not be located.
        </p>
        <Link href="/dashboard" className="crm-btn-primary">
          Return to Dashboard
        </Link>
      </div>
    </div>
  );
}
