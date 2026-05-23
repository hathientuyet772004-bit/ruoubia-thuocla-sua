import React, { useState } from 'react';
import axios from 'axios';
import { LockKeyhole } from 'lucide-react';

import { classifyApiError } from '../apiClient';

export default function AdminLogin({ onLogin }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const response = await axios.post('/api/auth/login', { password });
      onLogin(response.data);
    } catch (failure) {
      setError(classifyApiError(failure).message);
    } finally {
      setBusy(false);
    }
  };

  return <main className="admin-login"><form onSubmit={submit}><LockKeyhole /><h1>Trung tâm quản trị</h1><label>Mật khẩu quản trị<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoFocus required /></label>{error ? <p>{error}</p> : null}<button disabled={busy}>{busy ? 'Đang đăng nhập...' : 'Đăng nhập'}</button></form></main>;
}
