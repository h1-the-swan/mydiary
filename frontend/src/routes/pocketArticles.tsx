import React from "react";
import {
  Layout,
  Table,
  TableColumnType,
} from "antd";
import { PocketArticleRead, useReadPocketArticles, useReadTags } from "../api";

export default function PocketArticlesTable() {
  const { data: articles, isLoading } = useReadPocketArticles(
    { limit: 500 },
    {
      query: {
        select: (d) => d.data,
      },
    }
  );
  if (!articles) return null;
  const columns: TableColumnType<PocketArticleRead>[] = [
    {
      title: "id",
      dataIndex: "id",
      key: "id",
    },
    {
      title: "Title",
      dataIndex: "resolved_title",
      key: "resolved_title",
      render: (value, record) =>
        value ? value : "given_title: " + record.given_title,
    },
  ];
  return <Table dataSource={articles} columns={columns} />;
}
