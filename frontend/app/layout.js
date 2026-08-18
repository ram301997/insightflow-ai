import './globals.css';

export const metadata = {
  title: 'InsightFlow AI',
  description: 'Azure AI-powered conversational business intelligence',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
