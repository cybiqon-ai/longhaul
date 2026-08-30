import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Longhaul",
  description: "A day's work, every day, until it is done.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Applied before first paint so a dark-mode user never sees a white
            flash. Wrapped because storage throws outright in some contexts. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem("longhaul-theme");
              if(t==="dark"||(!t&&matchMedia("(prefers-color-scheme:dark)").matches))
              document.documentElement.classList.add("dark")}catch(e){}`,
          }}
        />
      </head>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
