export type GroupStatus = 'active' | 'inactive';
export type GroupType = 'internal';

export interface GroupListItem {
  id: string;
  name: string;
  description: string | null;
  status: GroupStatus;
  group_type: GroupType;
  member_count: number;
  created_at: string;
}

export interface Group {
  id: string;
  name: string;
  description: string | null;
  status: GroupStatus;
  group_type: GroupType;
  member_count: number;
  created_at: string;
  updated_at: string;
}

export interface GroupMember {
  id: string;
  user_id: string;
  email: string;
  full_name: string | null;
  status: string;
  added_at: string;
}

export interface GroupActivity {
  id: string;
  action: string;
  actor_id: string | null;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  created_at: string | null;
}

export interface GroupCreate {
  name: string;
  description?: string | null;
  status?: GroupStatus;
  group_type?: GroupType;
}

export interface GroupUpdate {
  name?: string;
  description?: string | null;
  status?: GroupStatus;
}

export interface Paginated<T> {
  data: T[];
  meta: { page: number; size: number; total: number; pages: number };
}
