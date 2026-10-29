/**
 * Everything the /services pages show: the service categories, the website
 * templates, the app showcase, the hardware catalogue and the licence list.
 *
 * Deliberately no prices. Hardware and licence prices move weekly and depend
 * on quantity, so every item ends in a "get a quote" that pre-fills the
 * contact form (see quoteHref) instead of a number that would go stale.
 */
import type { LucideIcon } from "lucide-react";
import {
  Globe,
  Smartphone,
  CodeXml,
  Server,
  KeyRound,
  Headphones,
  Bot,
  Laptop,
  Monitor,
  Cpu,
  HardDrive,
  ShieldCheck,
  Network,
  Wifi,
  Printer,
  BatteryCharging,
  Cctv,
  Keyboard,
  ShoppingBag,
  UtensilsCrossed,
  Building2,
  Stethoscope,
  GraduationCap,
  Palette,
  Rocket,
  Truck,
  Star,
  Clock,
  MapPin,
  Users,
  Sparkles,
  BarChart3,
  Lock,
  Leaf,
  Award,
  CalendarCheck,
  BookOpen,
  Zap,
  Layers,
  Gem,
  Home,
  HeartPulse,
} from "lucide-react";

/** A link to the contact form with the service and a starter message filled in. */
export function quoteHref(interest: string, message?: string) {
  const q = new URLSearchParams({ interest });
  if (message) q.set("message", message);
  return `/contact/?${q.toString()}`;
}

/* ------------------------------------------------------------------------ */
/* Service categories — the /services hub and the navbar dropdown             */
/* ------------------------------------------------------------------------ */

export type ServiceCategory = {
  title: string;
  href: string;
  icon: LucideIcon;
  short: string;
  desc: string;
  points: string[];
};

export const serviceCategories: ServiceCategory[] = [
  {
    title: "Website Development",
    href: "/services/website-development/",
    icon: Globe,
    short: "Ready templates or fully custom sites",
    desc: "Fast, modern, SEO-ready websites. Start from one of our ready-made templates or get a fully custom design.",
    points: ["8+ ready templates", "Mobile-first & SEO-ready", "Easy content editing"],
  },
  {
    title: "App & Custom Software",
    href: "/services/app-development/",
    icon: Smartphone,
    short: "Android, iOS, web apps and business software",
    desc: "Mobile apps, web apps and custom business software — CRM, inventory, HR, booking — built around how you work.",
    points: ["Android, iOS & web", "Admin dashboards", "Integrations & APIs"],
  },
  {
    title: "IT Hardware & Assets",
    href: "/services/it-hardware/",
    icon: Server,
    short: "Laptops, servers, firewalls and more",
    desc: "Laptops, desktops, servers, firewalls, networking, printers, UPS and CCTV — sourced, configured and delivered.",
    points: ["Leading brands", "Configured before delivery", "Warranty & AMC support"],
  },
  {
    title: "Software & Licenses",
    href: "/services/software-licenses/",
    icon: KeyRound,
    short: "Microsoft 365, Windows 11 Pro, Server & more",
    desc: "Genuine Microsoft 365, Windows, Windows Server, Office and other business software — licensed, deployed and renewed.",
    points: ["Genuine licenses", "Setup & migration", "Renewal management"],
  },
  {
    title: "Managed IT Services",
    href: "/managed-it-services-noida/",
    icon: Headphones,
    short: "Helpdesk, monitoring and support",
    desc: "Helpdesk, patching, monitoring and security for every device — we run your IT so your team can run the business.",
    points: ["Helpdesk & on-site", "Patching & monitoring", "Security baseline"],
  },
  {
    title: "AI IT Operations (SAVIO)",
    href: "/savio/",
    icon: Bot,
    short: "Self-healing IT with human approval",
    desc: "SAVIO, our AI System Administrator, detects and fixes common IT problems automatically — with approval where it matters.",
    points: ["Self-healing fixes", "Live telemetry", "Approval tiers"],
  },
];

/* ------------------------------------------------------------------------ */
/* Website templates                                                          */
/* ------------------------------------------------------------------------ */

// Metadata for the gallery. Each template's actual design lives in its own
// component under components/templates/ — they share nothing but this list.
export type SiteTemplate = {
  slug: string;
  name: string;
  industry: string;
  desc: string;
  tags: string[];
  swatches: string[];
  brand: string;
  highlights: string[];
};

export const siteTemplates: SiteTemplate[] = [
  {
    slug: "bazaar-ecommerce",
    name: "Bazaar",
    industry: "Fashion & lifestyle store",
    desc: "A full online store: hero slider, categories, flash-sale countdown, wishlist and a working cart drawer.",
    tags: ["E-commerce", "Motion"],
    swatches: ["#ff5a1f", "#16110b", "#fbf7f2"],
    brand: "bazaar",
    highlights: ["Working cart & drawer", "Sale countdown", "Auto hero slider"],
  },
  {
    slug: "voltix-3d-store",
    name: "Voltix",
    industry: "3D electronics store",
    desc: "A product page with a real-time 3D model you can rotate and recolour, plus specs and a model comparison.",
    tags: ["E-commerce", "3D"],
    swatches: ["#c8ff3d", "#07070c", "#1e4fd8"],
    brand: "voltix",
    highlights: ["Interactive 3D product", "Colour configurator", "Kinetic text"],
  },
  {
    slug: "nexus-corporate",
    name: "Nexus",
    industry: "Corporate & IT company",
    desc: "A confident B2B site with an isometric 3D hero, rotating headline, bento services grid and process timeline.",
    tags: ["Business", "3D"],
    swatches: ["#2457ff", "#0a1633", "#f6f8fc"],
    brand: "nexus-solutions",
    highlights: ["Isometric 3D layers", "Animated bento grid", "Client logo marquee"],
  },
  {
    slug: "launchly-saas",
    name: "Launchly",
    industry: "SaaS & startup",
    desc: "A dark, glowing product launch page with a 3D-tilted dashboard, live charts, pricing toggle and FAQ.",
    tags: ["Business", "Motion"],
    swatches: ["#7c5cff", "#3ee6ff", "#0b0920"],
    brand: "launchly",
    highlights: ["3D dashboard reveal", "Monthly/yearly pricing", "FAQ accordion"],
  },
  {
    slug: "studio-agency",
    name: "Studio/9",
    industry: "Creative agency & portfolio",
    desc: "A bold, editorial portfolio: giant kinetic type, morphing gradient blob, rotating badge and hover-reveal work.",
    tags: ["Creative", "Motion"],
    swatches: ["#ff2e88", "#0a0a0a", "#f3efe6"],
    brand: "studio9",
    highlights: ["Kinetic typography", "Morphing blob", "Hover-reveal projects"],
  },
  {
    slug: "spice-route-restaurant",
    name: "Spice Route",
    industry: "Restaurant & café",
    desc: "A warm fine-dining site with a turning plate and rising steam, tabbed menu and a live table reservation.",
    tags: ["Hospitality", "Motion"],
    swatches: ["#d9a24a", "#120c07", "#f5e9d7"],
    brand: "spiceroute",
    highlights: ["Animated plate & steam", "Tabbed menu", "Table booking"],
  },
  {
    slug: "haven-real-estate",
    name: "Haven",
    industry: "Real estate",
    desc: "Property search with a rising animated skyline, filterable listings and a live home-loan EMI calculator.",
    tags: ["Business", "Motion"],
    swatches: ["#1f4d3a", "#c7923e", "#f4efe6"],
    brand: "havenhomes",
    highlights: ["EMI calculator", "Listing filters", "Animated skyline"],
  },
  {
    slug: "careplus-clinic",
    name: "CarePlus",
    industry: "Clinic & hospital",
    desc: "A calm healthcare site with a live ECG monitor, 3-tap appointment booking and specialist profiles.",
    tags: ["Healthcare"],
    swatches: ["#0e9f9a", "#0d2b33", "#f2fbfa"],
    brand: "careplusclinic",
    highlights: ["Live ECG animation", "Appointment booking", "Doctor availability"],
  },
  {
    slug: "brightminds-school",
    name: "BrightMinds",
    industry: "School & coaching",
    desc: "A playful school site with floating shapes, a spinning admissions sticker, tilted course cards and polaroids.",
    tags: ["Education", "Motion"],
    swatches: ["#7b2ff7", "#ff4f8b", "#ffc93c"],
    brand: "brightminds",
    highlights: ["Playful motion", "Programs by age", "Admission steps"],
  },
];

export const getTemplate = (slug: string) => siteTemplates.find((t) => t.slug === slug);

/* ------------------------------------------------------------------------ */
/* App showcase                                                               */
/* ------------------------------------------------------------------------ */

export type AppScreen =
  | { kind: "stats"; title: string; greeting: string; cards: { label: string; value: string }[]; bars: number[]; rows: { title: string; sub: string; badge?: string }[] }
  | { kind: "list"; title: string; search?: string; rows: { title: string; sub: string; badge?: string; tone?: "ok" | "warn" | "info" }[] }
  | { kind: "slots"; title: string; subtitle: string; days: string[]; slots: string[]; button: string }
  | { kind: "steps"; title: string; subtitle: string; steps: { label: string; time: string; done: boolean }[]; button?: string }
  | { kind: "grid"; title: string; banner: string; items: { name: string; price: string }[] };

export type AppDemo = {
  slug: string;
  name: string;
  industry: string;
  desc: string;
  platforms: string[];
  icon: LucideIcon;
  from: string;
  to: string;
  features: string[];
  tabs: string[];
  screens: AppScreen[];
};

export const appDemos: AppDemo[] = [
  {
    slug: "fieldpro",
    name: "FieldPro",
    industry: "Field service & technicians",
    desc: "Assign jobs, track technicians live and close tickets with photos and customer sign-off.",
    platforms: ["Android", "iOS", "Admin web"],
    icon: Truck,
    from: "#2563eb",
    to: "#06b6d4",
    features: ["Job assignment & routing", "Photo + signature proof", "Offline mode", "Live technician tracking"],
    tabs: ["Today", "Jobs", "Job"],
    screens: [
      {
        kind: "stats",
        title: "Today",
        greeting: "Good morning, Rahul",
        cards: [
          { label: "Jobs today", value: "6" },
          { label: "Completed", value: "2" },
        ],
        bars: [30, 55, 40, 70, 50, 85, 60],
        rows: [
          { title: "AC service — Sector 62", sub: "10:30 AM · 3.2 km", badge: "Next" },
          { title: "Printer repair — Noida", sub: "12:00 PM · 5.1 km" },
        ],
      },
      {
        kind: "list",
        title: "My jobs",
        search: "Search jobs…",
        rows: [
          { title: "#2041 AC service", sub: "Sharma Residence", badge: "In progress", tone: "info" },
          { title: "#2038 Router install", sub: "Gupta Traders", badge: "Done", tone: "ok" },
          { title: "#2044 CCTV check", sub: "Metro Mart", badge: "Pending", tone: "warn" },
          { title: "#2045 Laptop setup", sub: "Apex Clinic", badge: "Pending", tone: "warn" },
        ],
      },
      {
        kind: "steps",
        title: "#2041 AC service",
        subtitle: "Sharma Residence · Sector 62",
        steps: [
          { label: "Reached location", time: "10:28", done: true },
          { label: "Inspection done", time: "10:41", done: true },
          { label: "Parts replaced", time: "—", done: false },
          { label: "Customer sign-off", time: "—", done: false },
        ],
        button: "Upload photo & complete",
      },
    ],
  },
  {
    slug: "shopease",
    name: "ShopEase",
    industry: "E-commerce & D2C",
    desc: "Your own branded shopping app with catalogue, offers, UPI checkout and order tracking.",
    platforms: ["Android", "iOS", "Web store"],
    icon: ShoppingBag,
    from: "#ea580c",
    to: "#f59e0b",
    features: ["Catalogue & offers", "UPI / card checkout", "Order tracking", "Push notifications"],
    tabs: ["Shop", "Orders", "Track"],
    screens: [
      {
        kind: "grid",
        title: "Discover",
        banner: "Festive sale · up to 40% off",
        items: [
          { name: "Cotton tee", price: "₹499" },
          { name: "Daily bag", price: "₹1,899" },
          { name: "Earbuds", price: "₹1,299" },
          { name: "Watch", price: "₹2,499" },
        ],
      },
      {
        kind: "list",
        title: "My orders",
        rows: [
          { title: "Wireless earbuds", sub: "Order #88213 · ₹1,299", badge: "Shipped", tone: "info" },
          { title: "Cotton tee × 2", sub: "Order #88102 · ₹998", badge: "Delivered", tone: "ok" },
          { title: "Daily bag", sub: "Order #87990 · ₹1,899", badge: "Delivered", tone: "ok" },
        ],
      },
      {
        kind: "steps",
        title: "Tracking #88213",
        subtitle: "Arriving tomorrow by 7 PM",
        steps: [
          { label: "Order placed", time: "Mon 2:10 PM", done: true },
          { label: "Packed", time: "Mon 6:45 PM", done: true },
          { label: "Shipped", time: "Tue 9:20 AM", done: true },
          { label: "Out for delivery", time: "—", done: false },
        ],
      },
    ],
  },
  {
    slug: "medibook",
    name: "MediBook",
    industry: "Clinic & appointments",
    desc: "Patients book slots, get reminders and view prescriptions; doctors see their day at a glance.",
    platforms: ["Android", "iOS", "Doctor web panel"],
    icon: Stethoscope,
    from: "#0891b2",
    to: "#10b981",
    features: ["Slot booking", "SMS / WhatsApp reminders", "Digital prescriptions", "Doctor dashboard"],
    tabs: ["Doctors", "Book", "Visits"],
    screens: [
      {
        kind: "list",
        title: "Find a doctor",
        search: "Search specialty…",
        rows: [
          { title: "Dr. A. Mehta", sub: "Cardiologist · 15 yrs", badge: "Today", tone: "ok" },
          { title: "Dr. S. Khan", sub: "Paediatrician · 11 yrs", badge: "Tomorrow", tone: "info" },
          { title: "Dr. R. Iyer", sub: "Orthopaedics · 18 yrs", badge: "Today", tone: "ok" },
        ],
      },
      {
        kind: "slots",
        title: "Dr. A. Mehta",
        subtitle: "Choose a time",
        days: ["Mon 3", "Tue 4", "Wed 5", "Thu 6"],
        slots: ["9:30", "10:00", "10:30", "11:30", "4:00", "4:30", "5:00", "6:30"],
        button: "Confirm booking",
      },
      {
        kind: "list",
        title: "My visits",
        rows: [
          { title: "Cardiology check-up", sub: "Tue 4 Nov · 10:30 AM", badge: "Upcoming", tone: "info" },
          { title: "General consultation", sub: "12 Oct · Prescription ready", badge: "Done", tone: "ok" },
        ],
      },
    ],
  },
  {
    slug: "stocksense",
    name: "StockSense",
    industry: "Inventory & warehouse",
    desc: "Real-time stock levels, barcode scanning, purchase orders and low-stock alerts across branches.",
    platforms: ["Android", "Web dashboard"],
    icon: BarChart3,
    from: "#4f46e5",
    to: "#22d3ee",
    features: ["Barcode / QR scanning", "Multi-branch stock", "Low-stock alerts", "Purchase orders"],
    tabs: ["Overview", "Items", "Alerts"],
    screens: [
      {
        kind: "stats",
        title: "Overview",
        greeting: "Main warehouse",
        cards: [
          { label: "SKUs", value: "1,284" },
          { label: "Low stock", value: "17" },
        ],
        bars: [60, 45, 80, 65, 90, 70, 75],
        rows: [
          { title: "Inward today", sub: "312 units · 4 suppliers" },
          { title: "Outward today", sub: "286 units · 39 orders" },
        ],
      },
      {
        kind: "list",
        title: "Items",
        search: "Scan or search…",
        rows: [
          { title: "Dell Latitude 5440", sub: "SKU LT-5440 · 24 in stock", badge: "OK", tone: "ok" },
          { title: "HP LaserJet toner", sub: "SKU TN-78A · 3 in stock", badge: "Low", tone: "warn" },
          { title: "Cat6 cable box", sub: "SKU CB-C6 · 41 in stock", badge: "OK", tone: "ok" },
        ],
      },
      {
        kind: "list",
        title: "Alerts",
        rows: [
          { title: "HP LaserJet toner", sub: "Below reorder level (5)", badge: "Reorder", tone: "warn" },
          { title: "PO #1182 received", sub: "48 units added", badge: "Done", tone: "ok" },
        ],
      },
    ],
  },
  {
    slug: "teamdesk",
    name: "TeamDesk",
    industry: "HR & attendance",
    desc: "Geo-fenced check-in, leave requests, approvals and payslips for your whole workforce.",
    platforms: ["Android", "iOS", "HR web panel"],
    icon: Users,
    from: "#7c3aed",
    to: "#ec4899",
    features: ["Geo-fenced check-in", "Leave & approvals", "Payslips", "Team calendar"],
    tabs: ["Home", "Leave", "Payslip"],
    screens: [
      {
        kind: "stats",
        title: "Home",
        greeting: "Hi Priya · checked in 9:02 AM",
        cards: [
          { label: "Present days", value: "19" },
          { label: "Leave left", value: "8" },
        ],
        bars: [80, 85, 78, 90, 88, 92, 86],
        rows: [
          { title: "Team stand-up", sub: "10:00 AM · Conference room" },
          { title: "Holiday: Diwali", sub: "Fri, 31 Oct", badge: "Holiday" },
        ],
      },
      {
        kind: "list",
        title: "Leave requests",
        rows: [
          { title: "Casual leave · 2 days", sub: "6–7 Nov · Family function", badge: "Pending", tone: "warn" },
          { title: "Sick leave · 1 day", sub: "14 Oct", badge: "Approved", tone: "ok" },
        ],
      },
      {
        kind: "steps",
        title: "October payslip",
        subtitle: "Credited on 1 Nov",
        steps: [
          { label: "Basic + HRA", time: "₹48,000", done: true },
          { label: "Allowances", time: "₹6,500", done: true },
          { label: "Deductions", time: "−₹5,200", done: true },
          { label: "Net pay", time: "₹49,300", done: true },
        ],
        button: "Download PDF",
      },
    ],
  },
  {
    slug: "edutrack",
    name: "EduTrack",
    industry: "School & coaching",
    desc: "Timetables, homework, attendance and fee reminders — one app for students, parents and teachers.",
    platforms: ["Android", "iOS", "Admin web"],
    icon: GraduationCap,
    from: "#f43f5e",
    to: "#f59e0b",
    features: ["Timetable & homework", "Attendance alerts", "Online fee payment", "Parent–teacher chat"],
    tabs: ["Today", "Homework", "Fees"],
    screens: [
      {
        kind: "stats",
        title: "Today",
        greeting: "Aarav · Class 8-B",
        cards: [
          { label: "Attendance", value: "96%" },
          { label: "Homework due", value: "2" },
        ],
        bars: [70, 82, 76, 88, 91, 85, 94],
        rows: [
          { title: "Maths", sub: "8:00 – 8:45 · Mr. Verma", badge: "Now" },
          { title: "Science", sub: "8:45 – 9:30 · Ms. Rao" },
        ],
      },
      {
        kind: "list",
        title: "Homework",
        rows: [
          { title: "Maths: Exercise 7.2", sub: "Due tomorrow", badge: "Due", tone: "warn" },
          { title: "English essay", sub: "Submitted", badge: "Done", tone: "ok" },
          { title: "Science project", sub: "Due Fri", badge: "Open", tone: "info" },
        ],
      },
      {
        kind: "steps",
        title: "Fees 2026–27",
        subtitle: "Term 2 due 10 Nov",
        steps: [
          { label: "Term 1", time: "Paid", done: true },
          { label: "Term 2", time: "₹18,500", done: false },
          { label: "Transport", time: "Paid", done: true },
        ],
        button: "Pay with UPI",
      },
    ],
  },
];

export const customSoftware = [
  { icon: Users, title: "CRM & sales", desc: "Leads, follow-ups, quotations and pipeline in one place." },
  { icon: BarChart3, title: "Inventory & billing", desc: "Stock, purchase, invoicing and reports across branches." },
  { icon: CalendarCheck, title: "Booking & scheduling", desc: "Appointments, resources and reminders." },
  { icon: Layers, title: "ERP & operations", desc: "Production, dispatch and approvals, end to end." },
  { icon: Headphones, title: "Helpdesk & ticketing", desc: "Customer or internal support with SLAs." },
  { icon: CodeXml, title: "Portals & dashboards", desc: "Customer, vendor and partner portals with live data." },
];

/* ------------------------------------------------------------------------ */
/* IT hardware catalogue                                                      */
/* ------------------------------------------------------------------------ */

export type HardwareItem = { name: string; brands: string; specs: string; tag?: string };
export type HardwareCategory = { key: string; title: string; icon: LucideIcon; blurb: string; items: HardwareItem[] };

export const hardwareCategories: HardwareCategory[] = [
  {
    key: "laptops",
    title: "Laptops",
    icon: Laptop,
    blurb: "Business laptops for every role — from everyday office work to engineering and design.",
    items: [
      { name: "Business laptops", brands: "Dell Latitude · HP ProBook / EliteBook · Lenovo ThinkPad", specs: "Intel Core i5/i7 or Ryzen 5/7 · 16–32 GB RAM · 512 GB–1 TB SSD · Windows 11 Pro", tag: "Most requested" },
      { name: "Thin & light / executive", brands: "Dell XPS · HP EliteBook x360 · Lenovo ThinkPad X1 · Apple MacBook Air", specs: "Premium build · long battery life · 14\" displays · fingerprint & IR login" },
      { name: "Budget & student", brands: "Dell Vostro · HP 250 series · Lenovo V / IdeaPad · Acer Aspire", specs: "Core i3/i5 · 8–16 GB RAM · 512 GB SSD · ideal for bulk deployment" },
      { name: "Mobile workstations", brands: "Dell Precision · HP ZBook · Lenovo ThinkPad P", specs: "NVIDIA RTX graphics · up to 64 GB RAM · ISV-certified for CAD & design" },
    ],
  },
  {
    key: "desktops",
    title: "Desktops & AIO",
    icon: Monitor,
    blurb: "Reliable desktops and space-saving all-in-ones for offices, counters and labs.",
    items: [
      { name: "Business desktops", brands: "Dell OptiPlex · HP Pro / Elite · Lenovo ThinkCentre", specs: "Tower, SFF and Micro form factors · Core i3–i7 · Windows 11 Pro", tag: "Bulk friendly" },
      { name: "All-in-one PCs", brands: "Dell OptiPlex AIO · HP ProOne · Lenovo ThinkCentre neo AIO", specs: "23.8\"–27\" FHD displays · built-in webcam · clean desks" },
      { name: "Thin clients & mini PCs", brands: "Dell · HP · Lenovo Tiny · Intel NUC-class", specs: "Low power · VDI-ready · mount behind monitors" },
    ],
  },
  {
    key: "workstations",
    title: "Workstations",
    icon: Cpu,
    blurb: "Power for CAD, rendering, video, data science and AI workloads.",
    items: [
      { name: "Tower workstations", brands: "Dell Precision · HP Z series · Lenovo ThinkStation", specs: "Intel Xeon / Core Ultra · NVIDIA RTX pro GPUs · ECC memory" },
      { name: "GPU / AI workstations", brands: "Custom builds · OEM GPU workstations", specs: "Multi-GPU configs · high-capacity NVMe · liquid cooling options" },
    ],
  },
  {
    key: "servers",
    title: "Servers",
    icon: Server,
    blurb: "Rack and tower servers for file sharing, ERP, virtualisation and backups.",
    items: [
      { name: "Tower servers", brands: "Dell PowerEdge T-series · HPE ProLiant ML · Lenovo ThinkSystem ST", specs: "Ideal for small offices · RAID storage · Windows Server or Linux", tag: "SMB favourite" },
      { name: "Rack servers", brands: "Dell PowerEdge R-series · HPE ProLiant DL · Lenovo ThinkSystem SR", specs: "1U/2U · dual Xeon / EPYC · redundant power · iDRAC / iLO remote management" },
      { name: "Virtualisation setups", brands: "VMware / Hyper-V / Proxmox ready", specs: "Sized, installed and configured with backups and monitoring" },
    ],
  },
  {
    key: "storage",
    title: "Storage & NAS",
    icon: HardDrive,
    blurb: "Shared storage and backup appliances so your data is always safe.",
    items: [
      { name: "NAS appliances", brands: "Synology · QNAP · WD", specs: "2–12 bays · RAID · snapshots · cloud sync", tag: "Backup ready" },
      { name: "SAN & enterprise storage", brands: "Dell PowerVault · HPE MSA", specs: "iSCSI / FC · high availability for virtual environments" },
      { name: "Drives & backup media", brands: "Seagate · WD · Samsung", specs: "Enterprise HDD, SSD, NVMe and external backup drives" },
    ],
  },
  {
    key: "firewalls",
    title: "Firewalls & Security",
    icon: ShieldCheck,
    blurb: "Next-generation firewalls and UTM appliances to protect your network edge.",
    items: [
      { name: "Next-gen firewalls", brands: "Fortinet FortiGate · Sophos XGS · Palo Alto Networks · SonicWall", specs: "IPS, web filtering, VPN, SD-WAN · sized to your users and bandwidth", tag: "Security essential" },
      { name: "Endpoint protection", brands: "Microsoft Defender · Sophos · Seqrite · ESET", specs: "Antivirus, EDR and device control for every laptop and desktop" },
      { name: "Secure remote access", brands: "SSL / IPsec VPN · ZTNA", specs: "Safe access for remote and hybrid staff" },
    ],
  },
  {
    key: "networking",
    title: "Switches & Routers",
    icon: Network,
    blurb: "Structured, managed networks that stay fast as you grow.",
    items: [
      { name: "Managed switches", brands: "Cisco · Aruba · Ubiquiti · TP-Link Omada · D-Link", specs: "8–48 ports · PoE / PoE+ · VLANs · 10G uplinks" },
      { name: "Routers & SD-WAN", brands: "Cisco · MikroTik · Fortinet · TP-Link", specs: "Dual-ISP failover · load balancing · branch connectivity" },
      { name: "Structured cabling", brands: "Cat6 / Cat6A · fibre · racks & patch panels", specs: "Designed, laid, labelled and tested" },
    ],
  },
  {
    key: "wifi",
    title: "Wi-Fi & Access Points",
    icon: Wifi,
    blurb: "Seamless office-wide Wi-Fi with central management and guest access.",
    items: [
      { name: "Wi-Fi 6 / 6E / 7 access points", brands: "Ubiquiti UniFi · Aruba Instant On · Cisco Meraki · TP-Link Omada", specs: "Ceiling & wall mount · roaming · captive portal for guests", tag: "Popular" },
      { name: "Outdoor & mesh", brands: "Ubiquiti · TP-Link · Ruijie", specs: "Campuses, warehouses and outdoor areas" },
    ],
  },
  {
    key: "printers",
    title: "Printers & Scanners",
    icon: Printer,
    blurb: "Office printing, scanning and copying — from desktop units to departmental MFPs.",
    items: [
      { name: "Laser printers & MFPs", brands: "HP LaserJet · Canon imageRUNNER · Brother · Epson", specs: "Mono and colour · duplex · network & mobile print" },
      { name: "Ink tank & receipt printers", brands: "Epson EcoTank · Canon PIXMA G · TVS · Zebra", specs: "Low cost per page · POS and label printing" },
      { name: "Document scanners", brands: "Canon · Epson · Fujitsu / Ricoh", specs: "High-speed duplex scanning to PDF and cloud" },
    ],
  },
  {
    key: "power",
    title: "UPS & Power",
    icon: BatteryCharging,
    blurb: "Protect your equipment and keep working through power cuts.",
    items: [
      { name: "Line-interactive UPS", brands: "APC · Eaton · Microtek · Luminous", specs: "600 VA – 3 kVA for desktops and network racks" },
      { name: "Online UPS", brands: "APC Smart-UPS · Eaton · Vertiv", specs: "1–20 kVA · servers and critical loads · battery banks" },
    ],
  },
  {
    key: "cctv",
    title: "CCTV & Surveillance",
    icon: Cctv,
    blurb: "IP cameras, recorders and remote viewing for offices, shops and warehouses.",
    items: [
      { name: "IP cameras & NVRs", brands: "Hikvision · CP Plus · Dahua · Axis", specs: "2–8 MP · night vision · mobile app viewing · 30-day recording" },
      { name: "Access control & biometrics", brands: "eSSL · ZKTeco · Matrix", specs: "Face / fingerprint attendance · door access" },
    ],
  },
  {
    key: "accessories",
    title: "Monitors & Accessories",
    icon: Keyboard,
    blurb: "Everything around the desk that makes people productive.",
    items: [
      { name: "Monitors", brands: "Dell · LG · Samsung · BenQ · ViewSonic", specs: "22\"–34\" · FHD to 4K · USB-C docking monitors" },
      { name: "Docks, keyboards & mice", brands: "Dell · HP · Logitech · Lenovo", specs: "USB-C / Thunderbolt docks · wireless combos" },
      { name: "Conference room", brands: "Logitech · Poly · Jabra · Yealink", specs: "Video bars, speakerphones and headsets for Teams / Zoom" },
    ],
  },
];

export const hardwareServices = [
  { icon: Sparkles, title: "Configured before delivery", desc: "Windows set up, apps installed, joined to your domain or Intune." },
  { icon: Award, title: "Asset tagging", desc: "Every device labelled and recorded for your asset register." },
  { icon: Truck, title: "Delivered & installed", desc: "Doorstep delivery and on-site installation." },
  { icon: ShieldCheck, title: "Warranty & AMC", desc: "We handle warranty claims and offer annual maintenance." },
];

export const hardwareBrands = [
  "Dell", "HP", "Lenovo", "Apple", "ASUS", "Acer", "HPE", "Cisco", "Fortinet", "Sophos",
  "Ubiquiti", "Aruba", "TP-Link", "Synology", "QNAP", "APC", "Eaton", "Hikvision", "Logitech", "Canon",
];

/* ------------------------------------------------------------------------ */
/* Software & licences                                                        */
/* ------------------------------------------------------------------------ */

export type License = { name: string; type: "Subscription" | "Perpetual" | "Add-on"; for: string; includes: string[]; tag?: string };
export type LicenseGroup = { key: string; title: string; icon: LucideIcon; blurb: string; items: License[] };

export const licenseGroups: LicenseGroup[] = [
  {
    key: "m365",
    title: "Microsoft 365",
    icon: Layers,
    blurb: "Email, Office apps, Teams and cloud storage — the productivity suite most businesses run on.",
    items: [
      { name: "Microsoft 365 Business Basic", type: "Subscription", for: "Email & collaboration on the web and mobile", includes: ["Business email (Exchange)", "Teams chat & meetings", "1 TB OneDrive per user", "Web & mobile Word, Excel, PowerPoint"] },
      { name: "Microsoft 365 Business Standard", type: "Subscription", for: "Everything in Basic plus desktop Office apps", includes: ["Desktop Word, Excel, PowerPoint, Outlook", "Business email & Teams", "1 TB OneDrive per user", "Webinars & bookings"], tag: "Most popular" },
      { name: "Microsoft 365 Business Premium", type: "Subscription", for: "Standard plus advanced security & device management", includes: ["Everything in Business Standard", "Intune device management", "Defender for Business", "Entra ID P1 & conditional access"], tag: "Best for security" },
      { name: "Microsoft 365 Apps for business", type: "Subscription", for: "Desktop Office apps without business email", includes: ["Desktop Word, Excel, PowerPoint, Outlook", "1 TB OneDrive per user", "Install on up to 5 PCs/Macs per user"] },
      { name: "Microsoft 365 E3 / E5", type: "Subscription", for: "Enterprise plans for larger organisations (300+ users)", includes: ["Office apps & enterprise email", "Advanced compliance", "Windows Enterprise rights", "E5: advanced security & Power BI Pro"] },
      { name: "Exchange Online Plan 1", type: "Subscription", for: "Business email only", includes: ["50 GB mailbox", "Calendar & contacts", "Anti-spam & anti-malware"] },
      { name: "Microsoft 365 Copilot", type: "Add-on", for: "AI assistant inside Word, Excel, Outlook and Teams", includes: ["Draft, summarise and analyse", "Works with your business data", "Add-on to eligible plans"], tag: "AI" },
    ],
  },
  {
    key: "windows",
    title: "Windows",
    icon: Monitor,
    blurb: "Genuine Windows for business PCs — upgrades, new devices and enterprise deployments.",
    items: [
      { name: "Windows 11 Pro", type: "Perpetual", for: "The business edition of Windows for every PC", includes: ["BitLocker encryption", "Domain / Entra join", "Remote Desktop host", "Group Policy & Intune"], tag: "Essential" },
      { name: "Windows 11 Pro upgrade", type: "Perpetual", for: "Move Windows 11 Home PCs to Pro", includes: ["Keeps apps & data", "Business features unlocked"] },
      { name: "Windows 11 Enterprise E3 / E5", type: "Subscription", for: "Per-user Windows Enterprise for managed fleets", includes: ["Advanced security features", "Long-term servicing options", "E5: Defender for Endpoint"] },
    ],
  },
  {
    key: "server",
    title: "Windows Server & SQL",
    icon: Server,
    blurb: "Licensing for on-premise and hybrid servers, sized correctly so you stay compliant.",
    items: [
      { name: "Windows Server 2025 Standard", type: "Perpetual", for: "Physical or lightly virtualised servers", includes: ["Core-based licensing", "2 VMs per full licence", "Hotpatching with Azure Arc"] },
      { name: "Windows Server 2025 Datacenter", type: "Perpetual", for: "Highly virtualised environments", includes: ["Unlimited VMs", "Storage Spaces Direct", "Software-defined networking"] },
      { name: "Windows Server CALs & RDS CALs", type: "Perpetual", for: "User / device access to your servers", includes: ["User or device CALs", "Remote Desktop Services CALs"] },
      { name: "SQL Server 2022", type: "Perpetual", for: "Databases for ERP, accounting and custom apps", includes: ["Standard & Enterprise editions", "Per-core or Server + CAL", "Azure-connected features"] },
    ],
  },
  {
    key: "office",
    title: "Office (one-time purchase)",
    icon: KeyRound,
    blurb: "Perpetual Office for PCs that don't need a subscription.",
    items: [
      { name: "Office Home & Business 2024", type: "Perpetual", for: "One PC or Mac, commercial use allowed", includes: ["Word, Excel, PowerPoint, Outlook", "One-time purchase", "Security updates"] },
      { name: "Office LTSC Professional Plus 2024", type: "Perpetual", for: "Volume licensing for organisations", includes: ["Word, Excel, PowerPoint, Outlook, Access", "Fixed feature set for regulated environments"] },
    ],
  },
  {
    key: "other-ms",
    title: "Other Microsoft products",
    icon: Sparkles,
    blurb: "Specialist tools and security add-ons from the Microsoft stack.",
    items: [
      { name: "Microsoft Intune", type: "Subscription", for: "Manage and secure laptops and phones", includes: ["Device enrolment", "App deployment", "Compliance policies"] },
      { name: "Defender for Business / Endpoint", type: "Subscription", for: "Endpoint protection with EDR", includes: ["Next-gen antivirus", "Attack-surface reduction", "Automated investigation"] },
      { name: "Entra ID P1 / P2", type: "Subscription", for: "Identity, single sign-on and MFA", includes: ["Conditional access", "SSO for SaaS apps", "P2: identity protection"] },
      { name: "Power BI Pro", type: "Subscription", for: "Business dashboards & reports", includes: ["Interactive reports", "Sharing & collaboration"] },
      { name: "Visio & Project", type: "Subscription", for: "Diagrams and project management", includes: ["Plan 1 / Plan 2 options", "Desktop and web apps"] },
      { name: "Teams Essentials / Teams Phone", type: "Subscription", for: "Meetings and business calling", includes: ["Group meetings up to 300", "Calling plans & devices"] },
    ],
  },
];

export const otherSoftware = [
  "Adobe Acrobat Pro", "Adobe Creative Cloud", "Autodesk AutoCAD", "Google Workspace",
  "Tally Prime", "Zoho Workplace", "Sophos / ESET endpoint", "VMware / Veeam backup",
];

export const licenseServices = [
  { icon: Sparkles, title: "Tenant setup", desc: "Domain, mailboxes, Teams and security defaults configured right." },
  { icon: Truck, title: "Email migration", desc: "Move from Gmail, cPanel or another host with zero lost mail." },
  { icon: BarChart3, title: "License right-sizing", desc: "Audit what you pay for and drop what you don't use." },
  { icon: CalendarCheck, title: "Renewal management", desc: "Reminders and renewals handled before anything lapses." },
];
