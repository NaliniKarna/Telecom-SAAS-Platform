/**
 * Solution content — the single source of truth for both the navigation
 * dropdown and the /solutions/:slug pages. Customer-focused copy only; no
 * technical/implementation detail is exposed here.
 */
export interface Solution {
  slug: string;
  title: string;
  tagline: string;
  comingSoon?: boolean;
  overview: string;
  benefits: { title: string; body: string }[];
  useCases: string[];
  howItHelps: string[];
}

export const SOLUTIONS: Solution[] = [
  {
    slug: 'bulk-sms',
    title: 'Bulk SMS',
    tagline: 'Reach large audiences reliably, in minutes.',
    overview:
      'Send high volumes of SMS to large contact lists in a single campaign — ' +
      'announcements, alerts, and updates delivered quickly and dependably to ' +
      'everyone who needs them.',
    benefits: [
      { title: 'Reach at scale', body: 'Message thousands of recipients from one campaign.' },
      { title: 'Personalized', body: 'Merge names and details so each message feels one-to-one.' },
      { title: 'Live delivery insight', body: 'Watch delivery and failure rates as the campaign runs.' },
      { title: 'Managed sender identity', body: 'Send under an approved, recognizable sender ID.' },
    ],
    useCases: [
      'Service announcements and outage notices',
      'Event reminders and RSVPs',
      'Emergency and mass alerts',
      'Payment, delivery, and status notifications',
    ],
    howItHelps: [
      'Organize recipients into contact lists or select them by tag.',
      'Compose from reusable templates with personalization fields.',
      'Choose an approved sender ID and send or schedule the campaign.',
      'Review delivery analytics to understand what landed.',
    ],
  },
  {
    slug: 'transactional-sms',
    title: 'Transactional SMS',
    tagline: 'Timely, per-event messages your customers trust.',
    overview:
      'Trigger individual, event-driven messages — order confirmations, receipts, ' +
      'and status updates — that reach customers the moment something happens.',
    benefits: [
      { title: 'Event-driven', body: 'Send the instant an order, booking, or update occurs.' },
      { title: 'Consistent branding', body: 'Every message goes out under your recognized sender ID.' },
      { title: 'Template-based', body: 'Define wording once for consistent, error-free messages.' },
      { title: 'Tracked', body: 'See the delivery status of each message.' },
    ],
    useCases: [
      'Order and booking confirmations',
      'Shipping and delivery updates',
      'Account and security notifications',
      'Appointment confirmations and reminders',
    ],
    howItHelps: [
      'Create templates for each type of notification.',
      'Send them through campaigns or the developer API.',
      'Keep messaging consistent and on-brand across every event.',
      'Monitor delivery so nothing goes unnoticed.',
    ],
  },
  {
    slug: 'otp-sms',
    title: 'OTP SMS',
    tagline: 'One-time passcodes that arrive when they matter.',
    overview:
      'Deliver one-time passcodes and verification messages promptly, so customers ' +
      'can sign in and confirm actions with confidence.',
    benefits: [
      { title: 'Prompt delivery', body: 'Get time-sensitive codes to customers quickly.' },
      { title: 'Reusable formats', body: 'Keep verification wording consistent with templates.' },
      { title: 'Clear status', body: 'Confirm that codes were delivered.' },
      { title: 'Trusted identity', body: 'Send under a sender ID customers recognize.' },
    ],
    useCases: [
      'Login and sign-up verification',
      'Transaction and payment confirmation',
      'Password resets',
      'Phone-number verification',
    ],
    howItHelps: [
      'Use a dedicated verification template and sender ID.',
      'Send codes as part of your sign-in or checkout flow.',
      'Track delivery to confirm codes are arriving.',
    ],
  },
  {
    slug: 'marketing-campaigns',
    title: 'Marketing Campaigns',
    tagline: 'Engage the right audience and measure what works.',
    overview:
      'Plan, personalize, and schedule promotional campaigns to the right segments, ' +
      'then measure results and refine your next send.',
    benefits: [
      { title: 'Segmentation', body: 'Target the right people using contact lists and tags.' },
      { title: 'Personalization', body: 'Tailor messages with merge fields for relevance.' },
      { title: 'Scheduling', body: 'Queue campaigns to go out at the ideal time.' },
      { title: 'Analytics', body: 'Measure delivery and engagement to improve over time.' },
    ],
    useCases: [
      'Promotions and limited-time offers',
      'Product launches and updates',
      'Seasonal and holiday campaigns',
      'Re-engagement of inactive customers',
    ],
    howItHelps: [
      'Build audience segments from your contacts.',
      'Craft on-brand, personalized templates.',
      'Schedule sends and let campaigns run automatically.',
      'Review analytics to sharpen the next campaign.',
    ],
  },
  {
    slug: 'voice',
    title: 'Voice Solutions',
    tagline: 'Automated and outbound voice.',
    comingSoon: false,
    overview:
      'Voice calling and campaigns are coming to Telecom Console: automated calls, ' +
      'voice broadcasts, and call flows managed from the same console you already use.',
    benefits: [
      { title: 'One console', body: 'Manage voice alongside your SMS programs.' },
      { title: 'Automated outreach', body: 'Reach audiences with voice broadcasts.' },
      { title: 'Consistent reporting', body: 'The same analytics approach you know.' },
    ],
    useCases: [
      'Voice announcements and reminders',
      'Automated outbound campaigns',
      'Interactive call flows',
    ],
    howItHelps: [
      'Built on the same platform foundation as your messaging.',
      'Register your company now so you are ready when it launches.',
    ],
  },
  {
    slug: 'missed-call',
    title: 'Missed Call Solutions',
    tagline: 'Missed-call capture and callbacks.',
    comingSoon: false,
    overview:
      'Missed-call services — turning a missed call into a signal for verification, ' +
      'lead capture, and callbacks — are on the Telecom Console roadmap.',
    benefits: [
      { title: 'Zero-cost engagement', body: 'Let customers reach you with a simple missed call.' },
      { title: 'Lead capture', body: 'Capture interest and follow up automatically.' },
      { title: 'Unified console', body: 'Managed alongside SMS and voice.' },
    ],
    useCases: [
      'Missed-call verification',
      'Lead capture and callbacks',
      'Opt-in and subscription flows',
    ],
    howItHelps: [
      'Part of the same platform as your other channels.',
      'Register your company now to be notified at launch.',
    ],
  },
];

export function solutionBySlug(slug: string): Solution | undefined {
  return SOLUTIONS.find((s) => s.slug === slug);
}
