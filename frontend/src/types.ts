export type Role = "admin" | "recruiter" | "client";
export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  agency_id: number;
  client_org_id: number | null;
  active: boolean;
  email_verified: boolean;
  mfa_enabled: boolean;
}
export interface Project {
  version: number;
  id: number;
  title: string;
  client_org_id: number;
  client_name: string;
  description: string;
  ideal_profile: string;
  agreement_terms: string;
  start_date: string | null;
  end_date: string | null;
  unread_count: number;
  created_at: string;
  archived_at?: string | null;
}
export interface ClientOrg {
  id: number;
  name: string;
}
export const stages = [
  "Identified",
  "Shortlisted",
  "Interviewing",
  "Offered",
  "Hired",
  "Rejected",
] as const;
export interface Candidate {
  version: number;
  id: number;
  name: string;
  current_role: string;
  company: string;
  summary: string;
  cv_url: string | null;
  stage: (typeof stages)[number];
  client_visible: boolean;
}
export interface Entry {
  id: number;
  author_id: number;
  author_name: string;
  body: string;
  created_at: string;
}
export interface Post extends Entry {
  attachment_url: string | null;
  comments: Entry[];
  comment_count?: number;
}
export interface DocumentLink {
  id: number;
  title: string;
  url: string;
}
export interface Milestone {
  version: number;
  id: number;
  title: string;
  description: string;
  target_date: string;
  completed: boolean;
}
export interface Invitation {
  id: number;
  email: string;
  role: Role;
  project_id: number | null;
  expires_at: string;
  used_at: string | null;
  revoked: boolean;
}

export interface Account {
  user: User;
  mfa_required: boolean;
  mfa_setup: boolean;
}
