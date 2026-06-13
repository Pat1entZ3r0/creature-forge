import type { DetailedHTMLProps, HTMLAttributes } from "react";

declare global {
  namespace JSX {
    interface IntrinsicElements {
      "model-viewer": DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement> & {
        src?: string;
        "animation-name"?: string;
        autoplay?: boolean;
        "camera-controls"?: boolean;
        "shadow-intensity"?: string | number;
        exposure?: string | number;
        "interaction-prompt"?: string;
      };
    }
  }
}
