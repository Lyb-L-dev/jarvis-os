import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Jarvis OS Tablet Terminal",
    short_name: "Jarvis",
    description: "Jarvis OS 小米平板专用终端",
    start_url: "/tablet",
    display: "standalone",
    background_color: "#020509",
    theme_color: "#020509",
    orientation: "landscape",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}
