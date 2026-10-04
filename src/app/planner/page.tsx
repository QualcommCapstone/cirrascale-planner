"use client";
import React, { useRef, useState } from "react";
import Link from "next/link";
import Markdown from "react-markdown";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { RainbowButton } from "@/components/ui/rainbow-button";
import FlipText from "@/components/ui/flip-text";
import ModeToggle from "../components/ModeToggle";
import { Send } from "lucide-react";

interface ChatMessage {
  id: number;
  content: string;
  sender: "user" | "ai";
}

export default function PlannerPage() {
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
    } catch (err) {
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
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-gray-100 to-gray-200 dark:from-gray-800 dark:to-gray-900">
      <header className="w-full py-4 px-6 flex justify-between items-center bg-white dark:bg-gray-900 shadow-md">
        <h1 className="text-2xl font-bold">
          <Link href="/">
            <FlipText word="PLANNER" />
          </Link>
        </h1>
        <ModeToggle />
      </header>

      <main className="flex-1 flex flex-col overflow-hidden bg-white dark:bg-gray-900">
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
                  className={`inline-block p-3 rounded-lg shadow-md prose lg:prose-base max-w-prose dark:prose-invert ${
                    message.sender === "user"
                      ? "bg-blue-500 text-white"
                      : "bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200"
                  }`}
                >
                  <Markdown>{message.content}</Markdown>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <Skeleton className="w-[220px] h-[40px] rounded-md" />
              </div>
            )}
          </div>
        </ScrollArea>

        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          <div className="mx-auto flex w-full max-w-3xl items-center space-x-2 rounded-lg bg-gray-100 dark:bg-gray-800 p-2">
            <Input
              type="text"
              placeholder="Describe your goal..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void send();
              }}
              className="flex-grow bg-transparent border-none focus-visible:ring-0"
            />
            <RainbowButton onClick={() => void send()} disabled={loading}>
              <Send className="h-4 w-4 mr-2" />
              Plan
            </RainbowButton>
          </div>
        </div>
      </main>
    </div>
  );
}
