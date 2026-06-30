import React from 'react';
import { Page, Panel, RouteLink } from '../shared/ui';

export default function UnknownPage({ navigate }) {
  return (
    <Page title="Không tìm thấy" subtitle="Đường dẫn này không tồn tại.">
      <Panel title="Quay lại">
        <RouteLink to="/dashboard" navigate={navigate}>Về trang tổng quan</RouteLink>
      </Panel>
    </Page>
  );
}
