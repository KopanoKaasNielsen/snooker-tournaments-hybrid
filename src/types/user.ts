export type Role = 'player' | 'organiser' | 'administrator';
export interface UserProfile {
  id: number;
  username: string;
  role: Role;
  player_id: number | null;
  is_active: boolean;
}
export interface SessionData {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
  user: UserProfile;
}
