"use client";

export default function Error({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="grid min-h-[100dvh] place-items-center bg-[#f3f2ee] px-6 text-[#171a16]">
      <section className="max-w-md border border-[#deddd6] bg-[#fbfaf6] p-6">
        <p className="text-xs uppercase tracking-[0.12em] text-[#687066]">Interface error</p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight">The workspace could not render.</h1>
        <p className="mt-3 text-sm leading-6 text-[#687066]">{error.message}</p>
        <button
          className="mt-5 rounded-[6px] bg-[#171a16] px-4 py-2 text-sm font-medium text-white"
          onClick={reset}
          type="button"
        >
          Retry
        </button>
      </section>
    </main>
  );
}
