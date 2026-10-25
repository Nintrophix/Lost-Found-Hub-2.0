import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

// Types mirror docs/api-contract.md.

export type Role = 'USER' | 'STAFF' | 'ADMIN';
export type AccountStatus = 'ACTIVE' | 'SUSPENDED' | 'DEACTIVATED';
export type ReportType = 'LOST' | 'FOUND';
export type ItemStatus = 'OPEN' | 'MATCHED' | 'CLAIMED' | 'RETURNED' | 'CLOSED';
export type ClaimStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'WITHDRAWN' | 'COMPLETED';
export type HandoverStatus = 'SCHEDULED' | 'VERIFIED' | 'COMPLETED' | 'CANCELLED';
export type MatchStatus = 'SUGGESTED' | 'CONFIRMED' | 'DISMISSED';
export type Counts = Record<string, number>;

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  email_verified: boolean;
  account_status: AccountStatus;
  campus_id: string | null;
  department: string | null;
  phone: string | null;
  created_at: string;
}

export interface RegisterInput {
  name: string;
  email: string;
  password: string;
  campus_id: string;
  department: string;
  phone: string | null;
}

export interface ProfileInput {
  name?: string;
  department?: string;
  phone?: string | null;
}

export interface SessionInfo {
  user: User | null;
  allowed_email_domains: string[];
}

export interface Reference {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
}

export interface ItemImage {
  id: number;
  url: string;
  content_type: string;
  file_size: number;
}

export interface Item {
  id: number;
  report_type: ReportType;
  title: string;
  description: string;
  category: { id: number; name: string };
  location: { id: number; name: string };
  color: string | null;
  brand: string | null;
  occurred_at: string;
  status: ItemStatus;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  images: ItemImage[];
  is_owner: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ItemInput {
  report_type?: ReportType;
  title: string;
  description: string;
  category_id: number;
  location_id: number;
  occurred_at: string;
  color: string | null;
  brand: string | null;
}

export interface MatchReason {
  signal: string;
  weight: number;
  value: number | null;
  points: number;
  detail: string;
}

export interface Match {
  id: number;
  score: number;
  status: MatchStatus;
  reasons: MatchReason[];
  lost_item_id: number;
  found_item_id: number;
  counterpart: Item;
}

export interface Person {
  id: number;
  name: string;
  email: string;
  campus_id: string | null;
}

export interface HandoverSummary {
  id: number;
  status: HandoverStatus;
  qr_expires_at: string | null;
  qr_used: boolean;
  verified_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface Claim {
  id: number;
  status: ClaimStatus;
  evidence: string;
  review_reason: string | null;
  reviewed_at: string | null;
  created_at: string;
  item: Item;
  handover: HandoverSummary | null;
  claimant?: Person;
}

export interface Handover extends HandoverSummary {
  claim_id: number;
  item_id: number;
  item_title: string;
  notes: string | null;
  claimant: Person;
}

export interface QrCode {
  payload: string;
  expires_at: string;
  svg: string;
}

export interface Notification {
  id: number;
  type: string;
  title: string;
  message: string;
  item_id: number | null;
  claim_id: number | null;
  read_at: string | null;
  created_at: string;
}

export interface PublicStats {
  open_lost_reports: number;
  found_items_waiting: number;
  items_returned: number;
}

export interface UserDashboard {
  reports: Record<ReportType, Counts>;
  recent_reports: Item[];
  claims: Counts;
  active_claims: Claim[];
  suggestion_count: number;
  top_suggestions: Match[];
  unread_notifications: number;
}

export interface StaffDashboard {
  pending_claims: number;
  oldest_pending_claim_at: string | null;
  approved_awaiting_handover: number;
  handovers: Counts;
  completed_last_7_days: number;
  open_found_reports: number;
  high_score_suggestions: number;
}

export interface AdminStats {
  users: { total: number; by_role: Counts; by_status: Counts; verified: number };
  reports: Record<ReportType, Counts>;
  claims: Counts;
  handovers: Counts;
  matches: Counts;
  by_category: { id: number; name: string; lost: number; found: number }[];
  by_location: { id: number; name: string; lost: number; found: number }[];
  monthly: { month: string; lost: number; found: number }[];
  found_return_rate: number | null;
  median_hours_to_return: number | null;
}

export interface AuditLog {
  id: number;
  actor_email: string | null;
  action: string;
  entity_type: string;
  entity_id: number | null;
  created_at: string;
}

export interface ItemQuery {
  q?: string;
  report_type?: ReportType | '';
  category_id?: number | null;
  location_id?: number | null;
  mine?: boolean;
  sort?: string;
  page?: number;
  page_size?: number;
}

/** Readable message from an API error ({"detail": ...} or a validation list). */
export function errorMessage(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    const detail = error.error?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.length) {
      const first = detail[0];
      const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : '';
      return field ? `${String(field).replace(/_/g, ' ')}: ${first.msg}` : first.msg;
    }
    if (error.status === 0) return 'Cannot reach the server. Check your connection and try again.';
    if (error.status === 413) return 'That file is too large.';
  }
  return 'Something went wrong. Please try again.';
}

function params(query: object): HttpParams {
  let result = new HttpParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '' && value !== false) {
      result = result.set(key, String(value));
    }
  }
  return result;
}

@Injectable({ providedIn: 'root' })
export class Api {
  private readonly http = inject(HttpClient);

  // Auth
  session(): Observable<SessionInfo> { return this.http.get<SessionInfo>('/api/auth/session'); }
  updateProfile(body: ProfileInput): Observable<User> { return this.http.patch<User>('/api/auth/me', body); }
  login(email: string, password: string): Observable<User> { return this.http.post<User>('/api/auth/login', { email, password }); }
  logout(): Observable<void> { return this.http.post<void>('/api/auth/logout', {}); }
  register(body: RegisterInput) { return this.http.post<{ message: string }>('/api/auth/register', body); }
  verifyEmail(token: string) { return this.http.post<{ message: string }>('/api/auth/verify-email', { token }); }
  resendVerification(email: string) { return this.http.post<{ message: string }>('/api/auth/resend-verification', { email }); }
  forgotPassword(email: string) { return this.http.post<{ message: string }>('/api/auth/password/forgot', { email }); }
  changePassword(current_password: string, new_password: string) {
    return this.http.post<{ message: string }>('/api/auth/password/change', { current_password, new_password });
  }
  resetPassword(token: string, new_password: string) { return this.http.post<{ message: string }>('/api/auth/password/reset', { token, new_password }); }

  // Reference and public data
  categories(): Observable<Reference[]> { return this.http.get<Reference[]>('/api/categories'); }
  locations(): Observable<Reference[]> { return this.http.get<Reference[]>('/api/locations'); }
  publicStats(): Observable<PublicStats> { return this.http.get<PublicStats>('/api/public-stats'); }

  // Items
  items(query: ItemQuery): Observable<Page<Item>> { return this.http.get<Page<Item>>('/api/items', { params: params(query) }); }
  item(id: number): Observable<Item> { return this.http.get<Item>(`/api/items/${id}`); }
  createItem(body: ItemInput): Observable<Item> { return this.http.post<Item>('/api/items', body); }
  closeItem(id: number): Observable<Item> { return this.http.post<Item>(`/api/items/${id}/close`, {}); }
  uploadImage(id: number, file: File): Observable<ItemImage> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<ItemImage>(`/api/items/${id}/images`, form);
  }

  // Matches
  itemMatches(id: number): Observable<Match[]> { return this.http.get<Match[]>(`/api/items/${id}/matches`); }
  confirmMatch(id: number): Observable<Match> { return this.http.post<Match>(`/api/matches/${id}/confirm`, {}); }
  dismissMatch(id: number): Observable<Match> { return this.http.post<Match>(`/api/matches/${id}/dismiss`, {}); }

  // Claims
  submitClaim(itemId: number, evidence: string): Observable<Claim> { return this.http.post<Claim>(`/api/items/${itemId}/claims`, { evidence }); }
  myClaims(): Observable<Claim[]> { return this.http.get<Claim[]>('/api/claims/mine'); }
  withdrawClaim(id: number): Observable<Claim> { return this.http.post<Claim>(`/api/claims/${id}/withdraw`, {}); }
  handoverQr(claimId: number): Observable<QrCode> { return this.http.post<QrCode>(`/api/claims/${claimId}/handover/qr`, {}); }

  // Dashboard and notifications
  dashboard(): Observable<UserDashboard> { return this.http.get<UserDashboard>('/api/dashboard'); }
  notifications(): Observable<Page<Notification> & { unread: number }> {
    return this.http.get<Page<Notification> & { unread: number }>('/api/notifications', { params: params({ page_size: 20 }) });
  }
  markRead(id: number) { return this.http.post<Notification>(`/api/notifications/${id}/read`, {}); }
  markAllRead() { return this.http.post<void>('/api/notifications/read-all', {}); }

  // Staff
  staffDashboard(): Observable<StaffDashboard> { return this.http.get<StaffDashboard>('/api/staff/dashboard'); }
  staffClaims(status: ClaimStatus): Observable<Page<Claim>> {
    return this.http.get<Page<Claim>>('/api/staff/claims', { params: params({ status, page_size: 50 }) });
  }
  approveClaim(id: number, reason: string | null) { return this.http.post<Claim>(`/api/staff/claims/${id}/approve`, { reason }); }
  rejectClaim(id: number, reason: string) { return this.http.post<Claim>(`/api/staff/claims/${id}/reject`, { reason }); }
  scheduleHandover(claimId: number, notes: string | null) { return this.http.post<Handover>(`/api/staff/claims/${claimId}/handover`, { notes }); }
  handovers(status: HandoverStatus): Observable<Page<Handover>> {
    return this.http.get<Page<Handover>>('/api/staff/handovers', { params: params({ status, page_size: 50 }) });
  }
  verifyHandover(payload: string): Observable<Handover> { return this.http.post<Handover>('/api/staff/handovers/verify', { payload }); }
  completeHandover(id: number, notes: string | null) {
    return this.http.post<Handover>(`/api/staff/handovers/${id}/complete`, { identity_confirmed: true, notes });
  }
  cancelHandover(id: number, reason: string) { return this.http.post<Handover>(`/api/staff/handovers/${id}/cancel`, { reason }); }

  // Admin
  adminStats(): Observable<AdminStats> { return this.http.get<AdminStats>('/api/admin/stats'); }
  adminUsers(q: string): Observable<Page<User>> { return this.http.get<Page<User>>('/api/admin/users', { params: params({ q, page_size: 50 }) }); }
  updateUser(id: number, body: { role?: Role; account_status?: AccountStatus }) { return this.http.patch<User>(`/api/admin/users/${id}`, body); }
  adminReference(kind: 'categories' | 'locations'): Observable<Reference[]> { return this.http.get<Reference[]>(`/api/admin/${kind}`); }
  createReference(kind: 'categories' | 'locations', name: string) { return this.http.post<Reference>(`/api/admin/${kind}`, { name }); }
  updateReference(kind: 'categories' | 'locations', id: number, body: Partial<Reference>) {
    return this.http.patch<Reference>(`/api/admin/${kind}/${id}`, body);
  }
  auditLogs(): Observable<Page<AuditLog>> { return this.http.get<Page<AuditLog>>('/api/admin/audit-logs', { params: params({ page_size: 50 }) }); }
}
