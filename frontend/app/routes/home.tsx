import type { Route } from "./+types/home";
import { DrugSearch } from "~/components/drug-search";

export function meta({}: Route.MetaArgs) {
  return [
    { title: "Drug Search Demo" },
    {
      name: "description",
      content: "Interactive UI for the DAW /search endpoint with live metrics.",
    },
  ];
}

export default function Home() {
  return (
    <main className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-8 md:py-12">
        <section className="mx-auto max-w-5xl space-y-6">
          <div className="flex justify-center">
            <img 
              src="/scriptsure-logo.png" 
              alt="ScriptSure" 
              className="h-12 w-auto"
            />
          </div>
        </section>

        <section className="mx-auto mt-8 max-w-4xl">
          <DrugSearch />
        </section>
      </div>
    </main>
  );
}
