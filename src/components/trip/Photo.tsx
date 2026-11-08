"use client";

import { useState } from "react";
import { ImageOff } from "lucide-react";
import { cn } from "@/lib/utils";
import { safeUrl } from "@/lib/trip/format";
import type { Photo as PhotoData } from "@/lib/trip/types";

interface Props {
  photo: PhotoData | null;
  alt: string;
  className?: string;
  /** Show the small "Photo: Wikimedia" credit link in a corner. */
  credit?: boolean;
  priority?: boolean;
}

/**
 * A Wikimedia photo that fills its (relatively positioned) parent. Hot-linked
 * thumbnails are plain <img>s on purpose: they're already sized by Wikimedia
 * and don't need the Next image optimizer or a remotePatterns entry.
 */
export function Photo({ photo, alt, className, credit = false, priority = false }: Props) {
  const [failed, setFailed] = useState(false);
  const src = safeUrl(photo?.url);
  const creditUrl = safeUrl(photo?.creditUrl);

  if (!src || failed) {
    return (
      <div
        className={cn(
          "absolute inset-0 flex items-center justify-center bg-muted text-muted-foreground/60",
          className
        )}
      >
        <ImageOff className="h-5 w-5" aria-hidden="true" />
      </div>
    );
  }

  return (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt}
        loading={priority ? "eager" : "lazy"}
        decoding="async"
        referrerPolicy="no-referrer"
        onError={() => setFailed(true)}
        className={cn("absolute inset-0 h-full w-full object-cover", className)}
      />
      {credit && creditUrl ? (
        <a
          href={creditUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="print-hidden absolute bottom-1.5 right-2 z-10 text-[10px] text-white/70 drop-shadow hover:text-white hover:underline"
        >
          Photo: Wikimedia
        </a>
      ) : null}
    </>
  );
}
