#include <stdio.h>
int main(void)
{
FILE *fp = fopen("nums.txt", "r");
int x;
if (fp == NULL)
{
printf("文件打开失败\n");
return 1;
}
fscanf(fp, "%d", &x);
printf("%d\n", x);
fclose(fp);
return 0;
}
