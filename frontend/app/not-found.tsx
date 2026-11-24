import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f4f8f5] p-6 text-center">
      <div className="max-w-md w-full bg-white border border-[#dfe8e1] rounded-2xl p-8 shadow-lg">
        <p className="text-[12px] font-medium uppercase tracking-wider text-[#65766a] mb-2">
          404 Not Found
        </p>
        <h1 className="text-[24px] font-semibold text-[#1d2b22] mb-3 leading-tight">
          Page not found
        </h1>
        <p className="text-[14px] text-[#65766a] mb-6 leading-relaxed">
          The dashboard resource or endpoint you requested could not be located.
        </p>
        <Link
          href="/"
          className="inline-flex items-center justify-center px-4 py-2 bg-[#2f6d46] hover:bg-[#285b3d] text-white text-[14px] font-medium rounded-lg transition-colors"
        >
          Return to Dashboard
        </Link>
      </div>
    </div>
  );
}
