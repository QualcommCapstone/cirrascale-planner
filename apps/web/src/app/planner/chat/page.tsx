"use client";
// Legacy markdown-plan chat. Preserved and reachable at /planner/chat but
// unlinked from the main navigation. Uses the original /api/plan endpoint.
import React, { useRef, useState } from "react";
import Link from "next/link";
import Markdown from "react-markdown";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { RainbowButton } from "@/components/ui/rainbow-button";
import FlipText from "@/components/ui/flip-text";
import ModeToggle from "../../components/ModeToggle";
import { Send } from "lucide-react";

interface ChatMessage {
  id: number;
  content: string;
  sender: "user" | "ai";
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 1,
      content:
        "Hi! Tell me a goal — a project, a trip, a launch, anything — and I'll turn it into a structured plan.",
      sender: "ai",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const nextId = useRef(2);

  const send = async () => {
    const goal = input.trim();
    if (!goal || loading) return;

    const userMsg: ChatMessage = { id: nextId.current++, content: goal, sender: "user" };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal }),
      });
      const data = await res.json();
      const content = res.ok
        ? data.plan
        : `**Sorry — I couldn't build a plan.**\n\n${data.error ?? "Unknown error."}`;
      setMessages((prev) => [
        ...prev,
        { id: nextId.current++, content, sender: "ai" },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: nextId.current++,
          content: "An error occurred while contacting the planner.",
          sender: "ai",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="flex w-full items-center justify-between border-b border-border px-6 py-4">
        <h1 className="text-2xl font-bold">
          <Link href="/">
            <FlipText word="PLANNER" />
          </Link>
        </h1>
        <ModeToggle />
      </header>

      <main className="flex flex-1 flex-col overflow-hidden">
        <ScrollArea className="flex-1 p-4">
          <div className="mx-auto w-full max-w-3xl">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`mb-4 flex ${
                  message.sender === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`prose prose-sm dark:prose-invert inline-block max-w-prose rounded-lg border border-border p-3 ${
                    message.sender === "user"
                      ? "bg-primary/10"
                      : "bg-card"
                  }`}
                >
                  <Markdown>{message.content}</Markdown>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <Skeleton className="h-[40px] w-[220px] rounded-md" />
              </div>
            )}
          </div>
        </ScrollArea>

        <div className="border-t border-border p-4">
          <div className="mx-auto flex w-full max-w-3xl items-center space-x-2 rounded-lg border border-border bg-card p-2">
            <Input
              type="text"
              placeholder="Describe your goal..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void send();
              }}
              className="flex-grow border-none bg-transparent focus-visible:ring-0"
            />
            <RainbowButton onClick={() => void send()} disabled={loading}>
              <Send className="mr-2 h-4 w-4" />
              Plan
            </RainbowButton>
          </div>
        </div>
      </main>
    </div>
  );
}
