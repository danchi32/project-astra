"use client";

import type { ComponentType } from "react";
import type { TplProps } from "./kit";
import Bazaar from "./Bazaar";
import Voltix from "./Voltix";
import Nexus from "./Nexus";
import Launchly from "./Launchly";
import Studio from "./Studio";
import SpiceRoute from "./SpiceRoute";
import Haven from "./Haven";
import CarePlus from "./CarePlus";
import BrightMinds from "./BrightMinds";

/** Slug (from siteTemplates in lib/services) → the template's own design. */
const templates: Record<string, ComponentType<TplProps>> = {
  "bazaar-ecommerce": Bazaar,
  "voltix-3d-store": Voltix,
  "nexus-corporate": Nexus,
  "launchly-saas": Launchly,
  "studio-agency": Studio,
  "spice-route-restaurant": SpiceRoute,
  "haven-real-estate": Haven,
  "careplus-clinic": CarePlus,
  "brightminds-school": BrightMinds,
};

export function Template({ slug, ...props }: TplProps & { slug: string }) {
  const T = templates[slug];
  return T ? <T {...props} /> : null;
}
