export const metadata = {
  title: "Privacy Policy — Virexa",
};

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-12 text-sm leading-7">
      <h1 className="text-2xl font-bold mb-4">Privacy Policy</h1>
      <p className="mb-4 text-zinc-600">Last updated: 2026-08-25</p>

      <h2 className="text-lg font-semibold mt-6 mb-2">1. What this app does</h2>
      <p className="mb-4">
        Virexa (operated by Sutan Rizki Ramdani) is an autonomous content
        operating system. It discovers trending topics, produces short-form
        video content, and publishes it to connected creator accounts (such as
        YouTube) on behalf of the account owner.
      </p>

      <h2 className="text-lg font-semibold mt-6 mb-2">2. Data we access</h2>
      <p className="mb-4">When you connect a creator account via OAuth:</p>
      <ul className="list-disc pl-6 mb-4">
        <li>Upload and manage videos on your behalf (youtube.upload)</li>
        <li>Read basic account info needed to verify uploads (youtube.readonly)</li>
      </ul>
      <p className="mb-4">
        We never see or store your account password. OAuth tokens are stored
        encrypted and used only to perform actions you have authorized.
      </p>

      <h2 className="text-lg font-semibold mt-6 mb-2">3. Content data</h2>
      <p className="mb-4">
        Content produced by the system (video files, scripts, analytics) is
        stored in the operator&apos;s own cloud storage (Cloudflare R2) and
        database (Neon Postgres).
      </p>

      <h2 className="text-lg font-semibold mt-6 mb-2">4. Contact</h2>
      <p>
        Questions about this policy: rizkiiramdaniii@gmail.com
      </p>
    </main>
  );
}
