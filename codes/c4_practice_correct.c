#include <stdio.h>
int main(void)
{
FILE *fp = fopen("data.txt", "w");
if (fp == NULL)
{
printf("文件打开失败\n");
return 1;
}
fprintf(fp, "%d\n", 100);
fclose(fp);
return 0;
}
